"""Precise serializer contracts, source-derived action fields and actual wire envelopes."""
import copy
import hashlib
import inspect
from typing import get_type_hints
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView
from drf_spectacular.openapi import AutoSchema
from .schema_contracts import request_contract, response_contract, computed_field_schema


class PharmacyAutoSchema(AutoSchema):
    def _get_serializer(self):
        view=self.view;declared=getattr(view,'serializer_class',None)
        untyped=isinstance(view,APIView) and not isinstance(view,GenericAPIView) and not declared and not callable(getattr(view,'get_serializer_class',None))
        if isinstance(view,GenericAPIView):
            try:declared=view.get_serializer_class()
            except (AttributeError,AssertionError):untyped=True
        if untyped or declared is serializers.Serializer:return None
        serializer=super()._get_serializer()
        model=getattr(getattr(serializer,'Meta',None),'model',None)
        if model and getattr(view,'swagger_fake_view',False) and getattr(view,'queryset',None) is None:
            view.queryset=model.objects.none()
        return serializer

    def get_operation(self, path, path_regex, path_prefix, method, registry):
        self.path=path;self.method=method.upper();self.registry=registry
        self._get_serializer()
        return super().get_operation(path,path_regex,path_prefix,method,registry)

    def _map_serializer_field(self, field, direction, bypass_extensions=False):
        if type(field).__name__=='VariantInventoryValueField':
            return {'type':'boolean'} if getattr(field,'coerce',None) is bool else {'type':'integer','minimum':0}
        if isinstance(field,serializers.ReadOnlyField):
            from .schema_contracts import model_attribute_schema
            model=getattr(getattr(field.parent,'Meta',None),'model',None)
            sources=getattr(field,'source_attrs',[]) or [field.field_name]
            if model and len(sources)==1:
                exact=model_attribute_schema(model,sources[0])
                if exact:return exact
                value=getattr(model,sources[0],None)
                if isinstance(value,property):return computed_field_schema(value.fget)
            return {'description':'Read-only computed JSON value.','x-ava-dynamic-field':True}
        return super()._map_serializer_field(field,direction,bypass_extensions)

    def _map_response_type_hint(self, method):
        from drf_spectacular.drainage import get_override
        try:explicit=get_override(method,'field') or get_type_hints(method).get('return')
        except (NameError,TypeError):explicit=None
        if explicit:return super()._map_response_type_hint(method)
        return computed_field_schema(method)

    def get_request_serializer(self):
        exact=self._get_serializer()
        return exact if exact is not None else request_contract(self.view,self.method)

    def get_response_serializers(self):
        exact=self._get_serializer()
        return exact if exact is not None else response_contract(self.view,self.method) or {'default':{'description':'Dynamic JSON action response.','x-ava-dynamic-json':True}}

    def _resolve(self,schema):
        if isinstance(schema,dict) and schema.get('$ref','').startswith('#/components/schemas/'):
            name=schema['$ref'].rsplit('/',1)[-1]
            component=self.registry._components.get((name,'schemas'))
            if component:return component.schema
        return schema

    def _get_response_for_code(self,serializer,status_code,media_types=None,direction='response'):
        result=super()._get_response_for_code(serializer,status_code,media_types,direction)
        if direction!='response' or str(status_code)=='204':return result
        for media,body in result.get('content',{}).items():
            if 'json' not in media:continue
            schema=body.get('schema',{});resolved=self._resolve(schema)
            if resolved.get('format')=='binary':continue
            props=resolved.get('properties',{})
            if 'success' in props or '/payments/mpesa/callback' in self.path or {'ResultCode','ResultDesc'}.issubset(props):continue
            if str(status_code).isdigit() and int(status_code)>=400:
                body['schema'] = {
                    'type':'object', 'required':['success','error'],
                    'properties': {
                        'success': {'type':'boolean','enum':[False]},
                        'error': {'type':'object','required':['code','message'], 'properties':{
                            'code':{'type':'string'}, 'message':{'type':'string'}, 'details':{}
                        }}
                    }
                }
                continue
            payload=copy.deepcopy(schema)
            paginated={'count','next','previous','results'}.issubset(props)
            if paginated:payload=copy.deepcopy(props['results'])
            if 'message' in props and len(props)>1:
                payload=copy.deepcopy(resolved);payload['properties'].pop('message',None)
                required=[k for k in payload.get('required',[]) if k!='message']
                if required:payload['required']=required
                else:payload.pop('required',None)
            envelope={'type':'object','required':['success','data','message'],'properties':{'success':{'type':'boolean','enum':[True]},'data':payload,'message':{'type':'string'}}}
            if paginated:envelope['properties']['meta']={'type':'object','properties':{'page':{'type':'integer'},'per_page':{'type':'integer'},'total':{'type':'integer'},'total_pages':{'type':'integer'},'next':{'type':'string','nullable':True},'previous':{'type':'string','nullable':True}}}
            body['schema']=envelope
        return result

    def get_operation_id(self):
        suffix=hashlib.sha256((self.method+' '+self.path).encode()).hexdigest()[:12]
        return super().get_operation_id()+'_'+suffix
