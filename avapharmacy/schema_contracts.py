"""Source-derived schemas for action handlers. No handler or business query is executed.
Existing validation serializers take precedence. Dynamic JSON remains explicitly JSON.
"""
import ast
import inspect
import textwrap
from functools import lru_cache
from rest_framework import serializers
from drf_spectacular.utils import inline_serializer
from drf_spectacular.types import OpenApiTypes


def _name(node):
    return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ''


@lru_cache(maxsize=512)
def handler_tree(cls, method):
    func = getattr(cls, method.lower(), None)
    if not func:
        return None, {}, {}
    func = inspect.unwrap(func)
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    except (OSError, TypeError, IndentationError, SyntaxError):
        return None, {}, {}
    bindings = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name): bindings[target.id] = node.value
    return tree, getattr(func, '__globals__', {}), bindings


def serializer_call(node, namespace, bindings, depth=0):
    if depth>5:return None
    if isinstance(node, ast.Name) and node.id in bindings:
        return serializer_call(bindings[node.id], namespace, bindings, depth+1)
    if isinstance(node, ast.Attribute) and node.attr=='data':
        return serializer_call(node.value, namespace, bindings, depth+1)
    if isinstance(node, ast.Call):
        cls=namespace.get(_name(node.func))
        if inspect.isclass(cls) and issubclass(cls, serializers.BaseSerializer):
            many=any(k.arg=='many' and isinstance(k.value,ast.Constant) and k.value.value is True for k in node.keywords)
            return cls(many=many)
    return None


def node_schema(node, namespace, bindings, depth=0):
    if depth>6:return {}
    exact=serializer_call(node,namespace,bindings)
    if exact is not None:return exact
    if isinstance(node,ast.Name) and node.id in bindings:
        return node_schema(bindings[node.id],namespace,bindings,depth+1)
    if isinstance(node,ast.Constant):
        if node.value is None:return {'nullable':True}
        if isinstance(node.value,bool):return {'type':'boolean'}
        if isinstance(node.value,int):return {'type':'integer'}
        if isinstance(node.value,float):return {'type':'number'}
        if isinstance(node.value,str):return {'type':'string'}
    if isinstance(node,ast.Dict):
        fields={}
        for key,value in zip(node.keys,node.values):
            if isinstance(key,ast.Constant) and isinstance(key.value,str):
                fields[key.value]=node_schema(value,namespace,bindings,depth+1)
        return ('object',fields)
    if isinstance(node,(ast.List,ast.Tuple,ast.ListComp)):
        child=node.elts[0] if hasattr(node,'elts') and node.elts else node.elt if isinstance(node,ast.ListComp) else None
        return ('array', node_schema(child,namespace,bindings,depth+1) if child else {})
    if isinstance(node,ast.JoinedStr):return {'type':'string'}
    if isinstance(node,ast.Compare):return {'type':'boolean'}
    if isinstance(node,ast.Attribute) and node.attr in {'id','pk','user_id','order_id'}:return {'type':'integer'}
    if isinstance(node,ast.Call):
        name=_name(node.func)
        if name in {'int','len','count'}:return {'type':'integer'}
        if name in {'bool','exists','has_permission'}:return {'type':'boolean'}
        if name in {'str','get_full_name','get_status_display','isoformat'}:return {'type':'string'}
        if name in {'float'}:return {'type':'number'}
        if name in {'list'}:return ('array',{})
        if name in {'dict'}:return ('object',{})
    return {}


def field_from_schema(spec, name):
    if isinstance(spec, serializers.BaseSerializer):
        spec.read_only=True; return spec
    if isinstance(spec,tuple):
        if spec[0]=='array':return serializers.ListField(child=field_from_schema(spec[1],name+'Item'),required=False)
        return inline_serializer(name=name,fields={k:field_from_schema(v,name+k.title().replace('_','')) for k,v in spec[1].items()})
    cls={'string':serializers.CharField,'integer':serializers.IntegerField,'number':serializers.FloatField,'boolean':serializers.BooleanField}.get(spec.get('type'))
    return cls(required=False,allow_null=True) if cls else serializers.JSONField(required=False,allow_null=True,help_text='Dynamic JSON value; the endpoint owns its business validation.')


@lru_cache(maxsize=512)
def _request_contract(cls, method):
    if method not in {'POST','PUT','PATCH'}:return None
    tree,namespace,bindings=handler_tree(cls,method)
    if tree is None:return None
    # Prefer the exact serializer used to validate request.data.
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and any(k.arg=='data' and isinstance(k.value,ast.Attribute) and k.value.attr=='data' for k in node.keywords):
            exact=serializer_call(node,namespace,bindings)
            if exact is not None:return exact
    fields={}
    for node in ast.walk(tree):
        key=None; file=False
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in {'get','getlist'}:
            source=ast.unparse(node.func.value)
            if source in {'request.data','request.FILES'} and node.args and isinstance(node.args[0],ast.Constant):
                key=node.args[0].value;file=source.endswith('FILES')
        elif isinstance(node,ast.Subscript) and ast.unparse(node.value)=='request.data' and isinstance(node.slice,ast.Constant):key=node.slice.value
        if isinstance(key,str):fields[key]=serializers.FileField(required=False) if file else serializers.JSONField(required=False,allow_null=True)
    if not fields:return None
    return inline_serializer(name=(cls.__module__.split('.')[-2].title()+cls.__name__)+method.title()+'ActionRequest',fields=fields)


@lru_cache(maxsize=512)
def _response_contract(cls, method):
    tree,namespace,bindings=handler_tree(cls,method)
    if tree is None:return None
    candidates={}
    for node in ast.walk(tree):
        if not isinstance(node,ast.Return) or not isinstance(node.value,ast.Call):continue
        call=node.value;name=_name(call.func)
        if name not in {'Response','FileResponse','HttpResponse'}:continue
        status='200'; status_node=next((k.value for k in call.keywords if k.arg=='status'),None)
        if isinstance(status_node,ast.Constant):status=str(status_node.value)
        elif isinstance(status_node,ast.Attribute):
            parts=status_node.attr.split('_');status=parts[1] if len(parts)>1 and parts[1].isdigit() else 'default'
        if name in {'FileResponse','HttpResponse'}:
            content_type=next((k.value.value for k in call.keywords if k.arg=='content_type' and isinstance(k.value,ast.Constant)),None)
            if name=='FileResponse' or content_type and content_type!='application/json':
                candidates[status]=OpenApiTypes.BINARY;continue
        if status.isdigit() and int(status)>=400:continue
        if status=='204' or not call.args:candidates[status]=None;continue
        spec=node_schema(call.args[0],namespace,bindings)
        if isinstance(spec,serializers.BaseSerializer):candidates[status]=spec
        elif isinstance(spec,tuple) and spec[0]=='object':
            candidates[status]=inline_serializer(name=(cls.__module__.split('.')[-2].title()+cls.__name__)+method.title()+'ActionResponse',fields={k:field_from_schema(v,(cls.__module__.split('.')[-2].title()+cls.__name__)+method.title()+k.title().replace('_','')) for k,v in spec[1].items()})
        elif isinstance(spec,tuple) and spec[0]=='array':
            child=field_from_schema(spec[1],(cls.__module__.split('.')[-2].title()+cls.__name__)+'Item')
            candidates[status]=type(child)(many=True) if isinstance(child,serializers.BaseSerializer) else {'type':'array','items':{}}
        elif spec:candidates[status]=spec
        else:candidates[status]={'description':'Dynamic JSON result returned by this action.','x-ava-dynamic-json':True}
    return candidates or None


def model_attribute_schema(model, attribute):
    if model is None:return None
    from django.db import models
    try:field=model._meta.get_field(attribute)
    except Exception:return None
    if isinstance(field,models.BooleanField):return {'type':'boolean'}
    if isinstance(field,(models.IntegerField,models.AutoField,models.ForeignKey)):return {'type':'integer','nullable':field.null}
    if isinstance(field,(models.DecimalField,models.FloatField)):return {'type':'number','nullable':field.null}
    if isinstance(field,models.DateTimeField):return {'type':'string','format':'date-time','nullable':field.null}
    if isinstance(field,models.DateField):return {'type':'string','format':'date','nullable':field.null}
    if isinstance(field,models.JSONField):return {'description':'JSON value'}
    return {'type':'string','nullable':field.null}


def computed_field_schema(method):
    """Infer source-backed scalar/container types; never pretend an unknown value is a string."""
    bound=getattr(method,'__self__',None)
    model=getattr(getattr(bound,'Meta',None),'model',None)
    if model is None:
        module=inspect.getmodule(method);owner=getattr(method,'__qualname__','').split('.')[0]
        candidate=getattr(module,owner,None)
        if hasattr(candidate,'_meta'):model=candidate
    try:tree=ast.parse(textwrap.dedent(inspect.getsource(inspect.unwrap(method))))
    except (OSError,TypeError,IndentationError,SyntaxError):return {'x-ava-dynamic-field':True,'description':'Computed JSON value.'}
    def infer(node):
        if isinstance(node,ast.Constant):
            if node.value is None:return {'nullable':True}
            return node_schema(node,{}, {})
        if isinstance(node,ast.JoinedStr):return {'type':'string'}
        if isinstance(node,ast.Compare) or isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Not):return {'type':'boolean'}
        if isinstance(node,ast.Attribute):
            return model_attribute_schema(model,node.attr) or {}
        if isinstance(node,ast.IfExp):return infer(node.body) or infer(node.orelse)
        if isinstance(node,(ast.List,ast.ListComp,ast.Tuple)):return {'type':'array','items':{}}
        if isinstance(node,ast.Dict):return {'type':'object','additionalProperties':True}
        if isinstance(node,ast.BoolOp):
            parts=[infer(v) for v in node.values];types={p.get('type') for p in parts if p.get('type')}
            return {'type':types.pop()} if len(types)==1 else {}
        if isinstance(node,ast.Call):
            name=_name(node.func)
            if name in {'int','len','count'}:return {'type':'integer'}
            if name in {'float','round','Decimal'}:return {'type':'number'}
            if name in {'str','strip','join','lower','upper','isoformat','strftime'} or name.startswith('get_') and name.endswith('_display'):return {'type':'string'}
            if name in {'bool','exists','has_permission','can_review'}:return {'type':'boolean'}
            if name in {'list','values','values_list'}:return {'type':'array','items':{}}
        return {}
    results=[infer(n.value) for n in ast.walk(tree) if isinstance(n,ast.Return) and n.value is not None]
    typed=[x for x in results if x.get('type')]
    types={x['type'] for x in typed}
    if len(types)==1:
        spec=next(x for x in typed if x['type']==next(iter(types))).copy()
        if any(x.get('nullable') for x in results):spec['nullable']=True
        return spec
    return {'x-ava-dynamic-field':True,'description':'Computed JSON value; no scalar type is asserted without source evidence.'}


def request_contract(view, method):
    return _request_contract(type(view),method)


def response_contract(view, method):
    return _response_contract(type(view),method)
