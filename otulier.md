import csv
import datetime as dt
import logging
import os.path
import qrcode
from barcode.writer import ImageWriter
from barcode import Code128
from collections import Counter
from django.db.models import Count, Q, Case, When, BooleanField
from openpyxl import load_workbook
from datetime import datetime
import json
import base64
import struct
from django.http import FileResponse, HttpResponseNotFound
from pathlib import Path
from django.db.models import Min

from django.contrib.auth.models import Group
from django.core.mail import send_mail, send_mass_mail
from urllib.parse import urlencode
import re
import unicodedata
from difflib import SequenceMatcher
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FileUploadParser
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.conf import settings
from django.contrib import messages
import os
import json
import shutil
import openpyxl
import pandas as pd
import pycountry
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import OuterRef, Subquery
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.list import ListView
from openpyxl import Workbook
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FileUploadParser
from rest_framework.views import APIView
from zipfile import ZipFile
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from rest_framework.permissions import AllowAny
from rest_framework.generics import GenericAPIView
from wsgiref.util import FileWrapper
import mimetypes
import zipfile
import shutil
from django.http import JsonResponse
from django.db.models import Q, Prefetch, Count
from .models import Job, JobTest, UnitCost
from django.db.models.functions import Lower
from django.db.models import Q
from django.core.paginator import Paginator
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import SimpleRateThrottle
from datetime import datetime, date
from collections import defaultdict

from .serializers import JobTestsSerializer, JobsSerializer
from django.db.models import Q
from django.core.paginator import Paginator
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, date


from django.core.paginator import Paginator
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from invoicing.utils import create_invoice
from jobs.constants import LDSF_FIELDS, PENDING, COMPLETED, IN_PROGRESS
from jobs.translation import translate_text
from jobs.models import *
from jobs.permissions import *
from jobs.raw_file_processor import RawFileProcess
from jobs.raw_file_writer import OpusFileWriter
from jobs.spectra_qc import run_job_spectra_qc

from jobs.serializers import *
from jobs.utils import *
from labs.models import LabInstrument
from notifications.constants import *
from notifications.data_api import create_notification
from users.models import CustomUser
from labs.models import LabTest
from .constants import PAGINATION_SIZE
from rest_framework.pagination import PageNumberPagination
from organization.models import Organization
from users.serializers import UserSerializer
from notifications.lims_mailer import send_bulk_emails
from notifications.models import Notification
from .models import Job, ProjectDocumentationUpload, Organization, Category

from django.views.generic import ListView
from django.db.models import Q
from itertools import groupby
from operator import attrgetter

import io as _io
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import DownloadToken
from django.utils import timezone
import dateutil.parser
        
User = get_user_model()

from operator import attrgetter


def parse_job_number(job_number):
    """
    Parses the job number into a format that can be easily sorted.
    Expected format: 'ICR-{middle}-{year}'
    """
    parts = job_number.split("-")
    # Handle cases where the job number format is not as expected.
    if len(parts) == 3:
        prefix, middle, year = parts
        # Attempt to convert middle and year parts to integers for proper sorting.
        try:
            middle = int(middle)
            year = int(year)
        except ValueError:
            # If conversion fails, default to 0 to ensure they are placed at the start.
            middle = 0
            year = 0
    else:
        prefix = job_number
        middle = 0
        year = 0

    return year, middle


class CustomPagination(PageNumberPagination):
    page_size = 10  # Set your desired page size here

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data["adjusted_elided_pages"] = self.get_adjusted_elided_pages()
        return response

    def get_adjusted_elided_pages(self):
        return "Your calculated value"


class JobViewSet(viewsets.ModelViewSet):
    """
    Vview for list, create, update and retrieve jobs
    """

    permission_classes = [JobPermission]
    PAGINATION_SIZE = 10

    def get_serializer_context(self):
        context = super(JobViewSet, self).get_serializer_context()
        context["instrument"] = self.request.query_params.get("instrument_id")
        return context

    def get_serializer_class(self):
        if self.action == "list":
            return JobListSerializer
        if self.action in ("create", "update", "retrieve"):
            return JobSerializer
        if self.action == "schedule":
            return JobScheduleSerializer

    def perform_create(self, serializer):
        return serializer.save(
            created_by=self.request.user,
            soil={"soil": int(self.request.data["samples_info"]["soil"])},
            plant={"plant": int(self.request.data["samples_info"]["plant"])},
            fertilizer={
                "fertilizer": int(self.request.data["samples_info"]["fertilizer"])
            },
            other={
                self.request.data["samples_info"]["other_description"]: int(
                    self.request.data["samples_info"]["other"]
                )
            },
        )

    template_name = "jobs.html"

    def get_queryset(self):
        queryset = Job.objects.select_related("organization").prefetch_related(
            "job_tests"
        )

        # Use a consistent method to check for Regional
        is_regional_admin = self.request.user.groups.filter(name="Regional Admin").exists()
        
        # Add better debugging information
        user_groups = list(self.request.user.groups.values_list('name', flat=True))
        username = getattr(self.request.user, 'username', '') or getattr(self.request.user, 'name', 'Unknown User')
        # print(f"User '{username}' has groups: {user_groups}")
        # print(f"Is Regional (using filter().exists()): {is_regional_admin}")
        organization_id =  self.request.user.organization.id

        # import pdb
        # pdb.set_trace()
        if is_regional_admin:
            if 'organization' in self.request.GET:
                # Get the organization value
                organization_in_req = self.request.GET.get('organization')
                queryset = queryset.filter(organization=organization_in_req)
                # Do something with the organization value
                # ...
            else:
                pass
            # For Regional Admin, filter by organization_id if provided
            # Otherwise, don't filter (show all organizations)
            # if organization_id:
            #     # print(f"Regional filtering by organization_id: {organization_id}")
            #     queryset = queryset.filter(organization_id=organization_id)
            # else:
            #     print("Regional viewing all organizations")
        else:
            # For non-Regional Admin, always filter by user's organization
            # print(f"Regular user filtering by their organization: {self.request.user.organization.id}")
            queryset = queryset.filter(organization=self.request.user.organization)
            
        # import pdb
        # pdb.set_trace()


        # Search functionality
        search = self.request.query_params.get("search")

        if search:
            sample_jobs = Sample.objects.filter(number__icontains=search).values("job")
            try:
                country = pycountry.countries.search_fuzzy(search)[0]
                country_code = country.alpha_2
            except LookupError:
                country_code = None
            queryset = queryset.filter(
                Q(job_number__icontains=search)
                | Q(scientist_name__icontains=search)
                | Q(scientist_email__icontains=search)
                | Q(sampling_design__icontains=search)
                | Q(country=country_code)
                | Q(region__icontains=search)
                | Q(project__icontains=search)
                | Q(site__icontains=search)
                | Q(organization__name__icontains=search)
                | Q(organization__email__icontains=search)
                | Q(organization__website_url__icontains=search)
                | Q(organization__physical_location__icontains=search)
                | Q(id__in=Subquery(sample_jobs))
            )

        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.request.query_params.get("page", 1)
        paginator = Paginator(queryset, 10)
        jobs = paginator.get_page(page)

        if request.accepted_renderer.format == "json":
            serializer = self.get_serializer(jobs, many=True)

            return Response(
                {
                    "results": serializer.data,
                    "pagination": {
                        "current_page": jobs.number,
                        "num_pages": jobs.paginator.num_pages,
                        "has_next": jobs.has_next(),
                        "has_previous": jobs.has_previous(),
                    },
                }
            )
        else:
            context = {
                "jobs_list": {
                    "page_obj": jobs,
                },
                "organizations": [],
                "results": jobs,
                # 'results': serializer.data,
            }
            
            # Use the same consistent check here as in get_queryset
            is_regional_admin = self.request.user.groups.filter(name="Regional Admin").exists()
            if is_regional_admin:
                organizations = Organization.objects.all()
                context["organizations"] = [
                    {
                        "id": org.id,
                        "name": org.name,
                        "country": pycountry.countries.get(alpha_2=org.country).name,
                    }
                    for org in organizations
                ]

            return render(request, "jobs.html", context)
    def calculate_total(samples_info):
        """
        Calculate the total of numerical values in a dictionary.

        Args:
        samples_info (dict): A dictionary containing sample information.

        Returns:
        int: The total of the numerical values in the dictionary.
        """
        return sum(
            value for key, value in samples_info.items() if isinstance(value, int)
        )

    def retrieve(self, request, *args, **kwargs):
        job = super(JobViewSet, self).retrieve(request, *args, **kwargs)

        if request.accepted_renderer.format == "html":
            reports = []
            job.template_name = "job.html"
            # total_samples = sum(value for key, value in samples_info.items() if isinstance(value, int))
            # total_samples = Sample.objects.filter(job_id=job.data["id"]).count()

            job.data = {"job": job.data}
            samples_info = job.data['job']['samples_info']

            total_samples = sum(value for value in samples_info.values() if isinstance(value, (int, float)) and value is not None)
 
            
            job.data["job"].update({"total_samples": total_samples})

        try:
            report_obj = ProjectDocumentationUpload.objects.filter(
                job=job.data["job"]["id"]
            )
            serializer = JobsProjectDocumentationUploadSerializer(report_obj, many=True)
            job.data["job"]["report"] = serializer.data
        except KeyError as e:
            report_obj = ProjectDocumentationUpload.objects.filter(job=job.data["id"])
            serializer = JobsProjectDocumentationUploadSerializer(report_obj, many=True)
            job.data["report"] = serializer.data

        job.data["user"] = self.request.user.organization.id

        return job

    def handle_serializer_errors(self,serializer):
        errors = {}
        for field, error_list in serializer.errors.items():
            if field == 'non_field_errors':
                errors['general'] = [str(error) for error in error_list]
            else:
                errors[field] = [str(error) for error in error_list]
        return errors

    def create(self, request, *args, **kwargs):

        try:
            serializer = self.get_serializer(
                data=request.data, context={"request": request}
            )
            date_str = request.data["samples_received_on"]
            
            # Check if the date string matches the format 'YYYY-MM-DDTHH:mm:ss.sssZ'
            if re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", date_str):
                # Convert the date string to the desired format 'YYYY-MM-DD'
                
                
                # strptime

                date_object =  timezone.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                formatted_date = date_object.strftime("%Y-%m-%d")
                request.data["samples_received_on"] = formatted_date
            elif "/" in date_str:
                # Convert the date string with '/' to 'YYYY-MM-DD'
                split_date = date_str.split("/")
                new_date = "{}-{}-{}".format(
                    split_date[2], split_date[0], split_date[1]
                )
                request.data["samples_received_on"] = new_date
            else:
                # Handle other cases or raise an exception if needed
                return JsonResponse({'Samples Received On': 'Invalid Date Format'}, status=status.HTTP_400_BAD_REQUEST)

            if request.data['report'] ==[]:
                return JsonResponse({'Reports': 'Please select at least one report'}, status=status.HTTP_400_BAD_REQUEST)
                

            if serializer.is_valid():
                job = self.perform_create(serializer)
                serialized_job = JobSerializer(job)
                permission = Permission.objects.get(codename="can_authorize_jobs")
                approvers = User.objects.filter(
                    Q(groups__permissions=permission) | Q(user_permissions=permission),
                    organization=request.user.organization,  is_active=True
                ).distinct()
                
                
                

                notification_data = []
                context = {
                        "name": User.objects.get(email=serialized_job.data['scientist_email']).name.capitalize() if serialized_job.data['scientist_email'] else '',
                        "link": request.build_absolute_uri(
                            reverse("scientists-compiled-data")
                        ),
                        "job_number": job.job_number,
                        "call_to_action": "View New Job",
                    }
                notification_data.append(
                        {
                            "user_to_notify":   User.objects.get(email=serialized_job.data['scientist_email']) if serialized_job.data['scientist_email'] else '',
                            "notification_type": NEW_JOB,
                            "email_subject": "LIMS New Job Submitted",
                            "email_context": context,
                        }
                    )
                # for approver in approvers:
                #     context = {
                #         "name": approver.name.capitalize(),
                #         "link": request.build_absolute_uri(
                #             reverse("job-detail", kwargs={"pk": job.pk})
                #         ),
                #         "job_number": job.job_number,
                #         "call_to_action": "Authorize New Job",
                #     }
                #     notification_data.append(
                #         {
                #             "user_to_notify": approver,
                #             "notification_type": NEW_JOB,
                #             "email_subject": "LIMS New Job Submitted",
                #             "email_context": context,
                #         }
                #     )
                    # notifications.append(notification)

                # Bulk create notifications
                with transaction.atomic():
                    notifications = Notification.objects.bulk_create(
                        [Notification(**data) for data in notification_data]
                    )


                # Send emails in bulk (non-blocking - don't fail job creation if email fails)
                try:
                    send_bulk_emails(notification_data)
                except Exception as email_error:
                    print(f"Warning: Failed to send email notifications: {email_error}")
                    # Log the error but don't fail the job creation

                return Response(serialized_job.data, status=status.HTTP_201_CREATED)
                
            else:
                errors = self.handle_serializer_errors(serializer)
                rr=errors.copy()
                
                # Custom handling for samples_status
                if 'samples_status' in rr and 'non_field_errors' in rr['samples_status']:
                    rr['samples_status'] = ['Kindly select one of the options']
                
                # Custom handling for test_ids
                if 'test_ids' in rr and rr['test_ids'][0] == 'This list may not be empty.':
                    rr['test_ids'] = ['Please select at least one test']
                    rr['tests'] = rr['test_ids']  # Create new key and copy value
                    del rr['test_ids']

                return JsonResponse(rr, status=status.HTTP_400_BAD_REQUEST)

    
        except Exception as e:
            print(str(e))
            return Response(str(e), status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def authorize(self, request, pk=None):
        try:
            with transaction.atomic():
                # First, get the relevant permissions
                can_authorize_jobs = Permission.objects.get(codename="can_authorize_jobs")
                can_view_jobs = Permission.objects.get(codename="can_view_jobs")

                # Then, use these permissions in your user query
                job_viewers = User.objects.filter(
                    (
                        Q(groups__permissions=can_authorize_jobs)
                        | Q(user_permissions=can_authorize_jobs)
                        | Q(groups__permissions=can_view_jobs)
                        | Q(user_permissions=can_view_jobs)
                    ),
                    organization=request.user.organization,
                ).distinct()

                job = self.get_object()
                scientist = User.objects.get(email=job.scientist_email)

                job.testing_authorized_by = request.user
                job.testing_authorized_at = timezone.now()
                job.save()

                # Create invoice (or get existing one)
                invoice, created = Invoice.objects.get_or_create(job=job)
                return Response(
                    {"testing_authorized_by": request.user.name}, status=status.HTTP_200_OK
                )
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return JsonResponse({"success": False, "error": str(e)})

    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        job = self.get_object()
        if "/" in request.data["start_date"]:
            start_date_list = request.data["start_date"].split("/")
            request.data["start_date"] = "{}-{}-{}".format(
                start_date_list[2], start_date_list[0], start_date_list[1]
            )
        if "/" in request.data["end_date"]:
            end_date_list = request.data["end_date"].split("/")
            request.data["end_date"] = "{}-{}-{}".format(
                end_date_list[2], end_date_list[0], end_date_list[1]
            )

        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        instrument_id = serializer.validated_data.pop("instrument_id")
        
        instrument_obj = get_object_or_404(LabInstrument, id=instrument_id)

        if instrument_obj.all_jobs == True:
            JobTest.objects.filter(job=job, test__test__instrument_id=instrument_id).update(
                **serializer.validated_data
            )
            # import pdb
            # pdb.set_trace()
            job_tests =  job.job_tests.filter(Q(job_id=job.id) & Q(test__test__name_category_id=1)  & Q(start_date__isnull=True))
            for job_test in job_tests:
                
                assignee = CustomUser.objects.get(id=request.data["assignee"])
      
                try:
                    job_test.start_date = request.data["start_date"]
                    job_test.end_date = request.data["end_date"]
                    job_test.assignee = assignee
                    job_test.save()
                    print(f"Successfully updated JobTest {job_test.id}")
                except Exception as e:
                    print(f"Error updating JobTest {job_test.id}: {str(e)}")
         
                
        else:

            JobTest.objects.filter(job=job, test__test__instrument_id=instrument_id).update(
                **serializer.validated_data
            )
        # send email to assignee
        notification_data = []
        data = serializer.validated_data
        context = {
            "name": data["assignee"].name,
            "link": f"{request.build_absolute_uri(reverse('job-list'))}/schedules/?instrument_id={instrument_id}",
            "job_number": job.job_number,
            "call_to_action": "View Assigned Task",
        }

        notification_data.append(
            {
                "user_to_notify": data["assignee"],
                "notification_type": TASK_ASSIGNED,
                "email_subject": "New Task Assigned",
                "email_context": context,
            }
        )
        # Bulk create notifications
        with transaction.atomic():
            notifications = Notification.objects.bulk_create(
                [Notification(**data) for data in notification_data]
            )

        # Send emails in bulk (non-blocking)
        try:
            send_bulk_emails(notification_data)
        except Exception as email_error:
            print(f"Warning: Failed to send email notifications: {email_error}")

        return Response(status=status.HTTP_200_OK)

    def start(self, request, pk=None):
        job = get_object_or_404(Job, pk=pk)
        instrument_id = request.query_params.get("instrument_id")
        instrument_obj = get_object_or_404(LabInstrument, id=instrument_id)
        
        
        if instrument_obj.all_jobs == True:
            job_tests = job.job_tests.filter(Q(test__test__instrument_id=instrument_id) | Q(test__test__name_category_id=1)  & Q(start_date__isnull=True))
        else:

            job_tests = job.job_tests.filter(test__test__instrument_id=instrument_id)

        if job_tests:
            for job_test in job_tests:
                if job_test.completion_status != 1:
                    job_test.completion_status = IN_PROGRESS
                    job_test.save()
        return Response(status=status.HTTP_200_OK)

    def complete(self, request, pk=None):
        job = self.get_object()

        instrument_id = request.query_params.get("instrument_id")
        instrument_obj = get_object_or_404(LabInstrument, id=instrument_id)
        
        
        # set status for that instrument as completed
        if instrument_obj.all_jobs == True:
            jobs_test_to_update = job.job_tests.filter(
               Q( test__test__instrument_id=instrument_id, completion_status=IN_PROGRESS) | Q(test__test__name_category_id=1)
            ).update(completion_status=COMPLETED)
        if instrument_obj.all_jobs == True:
            jobs_test_to_update = job.job_tests.filter(
               Q( test__test__instrument_id=instrument_id, completion_status=IN_PROGRESS) | Q(test__test__name_category_id=1)
            ).update(completion_status=COMPLETED)
        else:
            job.job_tests.filter(
                test__test__instrument_id=instrument_id, completion_status=IN_PROGRESS
            ).update(completion_status=COMPLETED)
        # update job status too if necessary
        if all([t.completion_status == COMPLETED for t in job.job_tests.all()]):
            job.completion_status = COMPLETED
            job.save()
        return Response(status=status.HTTP_200_OK)


    def opus_upload(self,files, pk, instrument):
        errors = []
        processed_ssns = set()
        zip_files_dir = os.path.join(
            settings.MEDIA_ROOT,
            "jobs/zip",
        )
        for file in files:
            location = zip_files_dir
            fs = OverwriteStorage(location=location)
            opus_filename = fs.save(os.path.join(str(pk), file.name), file)
            file_location = os.path.join(
                settings.MEDIA_ROOT, "jobs", "zip", opus_filename
            )

            # Define the raw_files directory for this job
            raw_files_dir = os.path.join(
                settings.MEDIA_ROOT, "jobs", "raw_files", str(pk)
            )
            # Delete the existing directory if it exists
            if os.path.exists(raw_files_dir):
                shutil.rmtree(raw_files_dir)

            # Define the updated_raw_files directory for this job
            updated_raw_files_dir = os.path.join(
                settings.MEDIA_ROOT, "jobs", "updated_opus_files", f"{pk}.zip"
            )
            # Delete the existing directory if it exists
            if os.path.exists(updated_raw_files_dir):
                # shutil.rmtree(updated_raw_files_dir)
                os.remove(updated_raw_files_dir)

            # Create a new directory
            os.makedirs(raw_files_dir, exist_ok=True)

            with ZipFile("{}".format(file_location), "r") as zipObj:
                # Extract all the contents of zip file to the newly created directory
                zipObj.extractall(raw_files_dir)
            try:
                raw_files_path = Path(raw_files_dir)
                
                file_names_to_process = [
                    str(file_path) for file_path in raw_files_path.rglob('*')
                    if file_path.is_file()
                ]
                
                if file_names_to_process:
                    processor = RawFileProcess(
                        job_id=str(pk),
                        file_names=file_names_to_process,
                        instrument=instrument.name,
                    )
                    result = processor.process()
                    if result:
                        errors.extend(result)
                    processed_ssns.update(processor.processed_ssns)
                else:
                    errors.append("No files found to process")
                    
            except FileNotFoundError as e:
                errors.append(f"Directory not found: {str(e)}")
            except PermissionError as e:
                errors.append(f"Permission denied: {str(e)}")
            except Exception as e:
                errors.append(f"An unexpected error occurred: {str(e)}")
                
        if errors:
            return JsonResponse({'errors': errors}, status=400)

        qc_report = run_job_spectra_qc(pk, flagged_by=self.request.user, processed_ssns=processed_ssns)

        try:
            job = Job.objects.select_related("organization").get(id=pk)
            regional_admins = CustomUser.objects.filter(
                groups__name="Regional Admin",
                organization=job.organization,
                is_active=True,
            )
            now = timezone.now().strftime("%Y-%m-%d %H:%M UTC")
            uploaded_by_name = getattr(self.request.user, "name", str(self.request.user))
            notifications = [
                {
                    "user_to_notify": admin,
                    "notification_type": OPUS_FILES_UPLOADED,
                    "email_subject": f"OPUS files uploaded – {job.site} ({job.job_number})",
                    "email_context": {
                        "name": admin.name,
                        "job_number": job.job_number,
                        "site": job.site,
                        "file_count": len(files),
                        "uploaded_by": uploaded_by_name,
                        "uploaded_at": now,
                    },
                }
                for admin in regional_admins
            ]
            if notifications:
                send_bulk_emails(notifications)
        except Exception:
            pass

        try:
            job = Job.objects.select_related("organization").get(id=pk)
            outlier_ssns = qc_report.get("flagged_ssns", [])
            if outlier_ssns:
                admin_users = list(
                    CustomUser.objects.filter(is_superuser=True, is_active=True)
                )
                regional_admins = list(
                    CustomUser.objects.filter(
                        groups__name="Regional Admin",
                        organization=job.organization,
                        is_active=True,
                    )
                )
                recipients = {user.id: user for user in admin_users + regional_admins}.values()
                tagged_at = timezone.now().strftime("%Y-%m-%d %H:%M UTC")
                uploaded_by_name = getattr(self.request.user, "name", str(self.request.user))
                notifications = [
                    {
                        "user_to_notify": recipient,
                        "notification_type": SPECTRA_OUTLIER_TAGGED,
                        "email_subject": f"Spectra outlier tagged - {job.site} ({job.job_number})",
                        "email_context": {
                            "name": recipient.name,
                            "job_number": job.job_number,
                            "site": job.site,
                            "flagged_count": len(outlier_ssns),
                            "flagged_ssns": outlier_ssns,
                            "uploaded_by": uploaded_by_name,
                            "tagged_at": tagged_at,
                        },
                    }
                    for recipient in recipients
                ]
                if notifications:
                    Notification.objects.bulk_create([Notification(**data) for data in notifications])
                    send_bulk_emails(notifications)
        except Exception:
            pass

        return JsonResponse({
            'message': 'Files processed successfully',
            'qc_report': qc_report,
        }, status=200)




    
    
    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FileUploadParser],
    )
    def upload_data(self, request, pk=None):
        lab_instr = LabInstrument.objects.get(id=request.POST.get("instrument_id"))
        image_files = request.FILES.getlist("files")
        
        
        

        if lab_instr.is_living_soils == True:
            image = request.FILES.get("files")
            living_files_dir = os.path.join(
                settings.MEDIA_ROOT,
                "jobs/zip",
            )
            location = living_files_dir
            fs = OverwriteStorageLivingSoilsImage(location=location)
            for file in image_files:
                fs = FileSystemStorage()

                DataUpload.objects.create(
                    job_id=pk,
                    instrument=lab_instr,
                    uploaded_file=os.path.join(
                        "jobs",
                        "data",
                        "living_soils",
                        lab_instr.name.lower().replace(" ", "_"),
                        str(pk),
                        file.name.lower().replace(" ", "_"),
                    ),
                )
                file_saved = fs.save(
                    os.path.join(
                        "jobs",
                        "data",
                        "living_soils",
                        lab_instr.name.lower().replace(" ", "_"),
                        str(pk),
                        file.name.lower().replace(" ", "_"),
                    ),
                    file,
                )
                instrument = LabInstrument.objects.get(pk=lab_instr.id)
                fileurl = fs.url(DataUpload)

                if "xlsx" not in file.name:
                    with open(
                        os.path.join(settings.BASE_DIR, "media", file_saved), "rb"
                    ) as img_file:
                        base64_image = base64.b64encode(img_file.read())
                        job_id = Job.objects.get(id=pk)
                        LivingSoilsImagesModel.objects.create(
                            job_id=job_id, image=base64_image
                        )
        
        
        
        try:
            files = request.FILES.getlist("files")
            instrument_id = request.POST.get("instrument_id")
            instrument = LabInstrument.objects.get(pk=instrument_id)
            if instrument.is_active == False:
                verion_one_instruments_upload(files, instrument, pk)
            
            
            if instrument.is_pxrf == True:
                files = request.FILES.getlist("files")

                pxrf_files_dir = os.path.join(
                    settings.MEDIA_ROOT,
                    "jobs/data/pXRF",
                )
                location = pxrf_files_dir
                fs = FileSystemStorage()
                for file in files:
                    file_saved = fs.save(
                        os.path.join(
                            "jobs",
                            "data",
                            "pXRF",
                            str(pk),
                            file.name.lower().replace(" ", "_"),
                        ),
                        file,
                    )

            if instrument.is_wetchemistry == True:
                return process_wetchem_files(self, instrument, files, pk)

            if instrument.opus_output and instrument.is_active:
                
                return self.opus_upload(files, pk, instrument)
            return JsonResponse({'message': 'No files to process'}, status=200)
        except Exception as e:
            print(
                str(e),
                "exceptionnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn",
            )
            return JsonResponse({"error": str(e)}, status=400)




class uploadViewSet(viewsets.ModelViewSet):
    def simple_upload(self, request):
        files = request.FILES.getlist("files")
        fs = FileSystemStorage()
        # for file in files:

        file_path = fs.save(os.path.join("units", files[0].name), files[0])
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        dd = []
        csv_file = pd.read_csv(full_path, encoding="latin-1")
        for data in csv_file.to_dict("records"):
            if "pH" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)
            if "EC.S" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)
            if "ExAc" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.P" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.K" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.Ca" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.Mg" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.Mn" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.S" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.Cu" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.B" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.Zn" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.Al" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.Na" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "m3.Fe" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "CEC" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "PSI" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "Sand" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "Silt" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "Clay" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "Nitrogen.Content" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "d15NAIR" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "Carbon.Content" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

            if "d13CV.PDB" in data["Variables"]:
                cc = {
                    data["Variables"]: {
                        "unit_one_variable": data["Variables"],
                        "unit_one_description": data["Description"],
                        "unit_one_unit": data["Units"],
                    }
                }
                dd.append(cc)

        WetChemSampleDataUnits.objects.create(
            ph_unit_name=dd[0]["pH"],
            ec_salts_unit_name=dd[1]["EC.S"],
            exchangeable_acidity_unit_name=dd[2]["ExAc"],
            phosphorus_unit_name=dd[3]["m3.P"],
            potassium_unit_name=dd[4]["m3.K"],
            calcium_unit_name=dd[5]["m3.Ca"],
            magnesium_unit_name=dd[6]["m3.Mg"],
            manganese_unit_name=dd[7]["m3.Mn"],
            sulphur_unit_name=dd[8]["m3.S"],
            copper_unit_name=dd[9]["m3.Cu"],
            boron_unit_name=dd[10]["m3.B"],
            zinc_unit_name=dd[11]["m3.Zn"],
            aluminium_unit_name=dd[12]["m3.Al"],
            sodium_unit_name=dd[13]["m3.Na"],
            iron_unit_name=dd[14]["m3.Fe"],
            cec_unit_name=dd[15]["CEC"],
            phosphorus_sorption_index_unit_name=dd[16]["PSI"],
            sand_unit_name=dd[17]["Sand"],
            silt_unit_name=dd[18]["Silt"],
            clay_unit_name=dd[19]["Clay"],
            nitrogen_unit_name=dd[20]["Nitrogen.Content"],
            d15NAIR_unit_name=dd[21]["d15NAIR"],
            carbon_unit_name=dd[22]["Carbon.Content"],
            d13CV_unit_name=dd[23]["d13CV.PDB"],
        )

        return Response(status=status.HTTP_202_ACCEPTED)



class JobScripts(viewsets.ModelViewSet):
    permission_classes = [AllowAny]

    @action(detail=True, methods=["delete"])
    def job_samples_delete(self, request):
        try:
            job_number = request.data["job_number"]
            sample = Sample.objects.filter(job_id__job_number=job_number)
            sample.delete()
            return Response("deleted")
        except Exception as e:
            return Response("err", str(e))






LDSF_HEADER_ALIASES = {
    "cluster": "cluster",
    "groupe": "cluster",
    "plot": "plot",
    "parcelle": "plot",
    "depth_std": "depth_std",
    "profondeur_std": "depth_std",
    "profondeur_standard": "depth_std",
    "depth_top": "depth_top",
    "profondeur_haut": "depth_top",
    "profondeur_superieure": "depth_top",
    "depth_bottom": "depth_bottom",
    "profondeur_bas": "depth_bottom",
    "profondeur_inferieure": "depth_bottom",
    "air_dried_wt": "air_dried_wt",
    "poids_seche_air": "air_dried_wt",
    "coarse_wt": "coarse_wt",
    "poids_grossier": "coarse_wt",
}

NON_LDSF_HEADER_ALIASES = {
    "groupe": "Cluster",
    "parcelle": "Plot",
    "profondeur_std": "Depth_Std",
    "profondeur_standard": "Depth_Standard",
    "profondeur_haut": "Depth_Top",
    "profondeur_superieure": "Depth_Top",
    "profondeur_bas": "Depth_Bottom",
    "profondeur_inferieure": "Depth_Bottom",
    "poids_seche_air": "Air_dried_wt",
    "poids_grossier": "Coarse_wt",
    "traitement": "treat",
    "laboratoire": "lab",
    "compartiment": "Compart",
    "baie": "Bay",
    "plateau": "Tray",
    "position": "Pos",
    "poids": "Wt",
}

FRENCH_WORD_ALIASES = {
    "nom": "name",
    "numero": "number",
    "no": "number",
    "le": "",
    "la": "",
    "les": "",
    "de": "",
    "du": "",
    "des": "",
    "d": "",
    "echantillon": "sample",
    "etude": "study",
    "scientifique": "scientist",
    "site": "site",
    "region": "region",
    "pays": "country",
    "materiau": "material",
    "materiel": "material",
    "echantillonnage": "sampling",
    "date": "date",
    "profondeur": "depth",
    "haut": "top",
    "bas": "bottom",
    "poids": "weight",
    "sol": "soil",
    "terre": "earth",
    "traitement": "treatment",
    "laboratoire": "lab",
    "commentaire": "comment",
    "description": "description",
}

def _normalize_header_value(value):
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace(" ", "_")
    text = re.sub(r"[^\w]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _map_ldsf_headers(header_cells):
    mapped = []
    for cell in header_cells:
        if not cell.value:
            continue
        normalized = _normalize_header_value(cell.value)
        if not normalized:
            continue
        mapped.append(LDSF_HEADER_ALIASES.get(normalized, normalized))
    return mapped


def _build_ldsf_header_label_map(header_cells):
    label_map = {}
    for cell in header_cells:
        if not cell.value:
            continue
        normalized = _normalize_header_value(cell.value)
        if not normalized:
            continue
        canonical = LDSF_HEADER_ALIASES.get(normalized, normalized)
        label_map[canonical] = cell.value
    return label_map


def _is_number_value(value):
    if value is None or value == "":
        return True
    if isinstance(value, (int, float)):
        return True
    try:
        float(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _map_non_ldsf_headers(header_cells):
    mapped = []
    for cell in header_cells:
        if not cell.value:
            continue
        raw_value = str(cell.value).strip()
        normalized = _normalize_header_value(raw_value)
        if normalized in NON_LDSF_HEADER_ALIASES:
            mapped.append(NON_LDSF_HEADER_ALIASES[normalized])
            continue
        mapped.append(_translate_custom_field_name(raw_value))
    return mapped


def _englishify_header(value):
    normalized = _normalize_header_value(value)
    if not normalized:
        return ""
    words = normalized.split("_")
    translated = [FRENCH_WORD_ALIASES.get(word, word) for word in words]
    return "_".join(word.capitalize() for word in translated if word)

def _translate_custom_field_name(value):
    raw = str(value).strip()
    if not raw:
        return ""
    normalized = _normalize_header_value(raw)
    if not normalized:
        return ""
    words = normalized.split("_")
    has_french_words = any(word in FRENCH_WORD_ALIASES for word in words)
    if has_french_words:
        return _translate_header_to_english(raw)
    return _englishify_header(raw)


def _lookup_custom_field_alias(normalized, organization):
    if not normalized:
        return None
    if organization:
        alias = CustomFieldAlias.objects.filter(
            normalized_alias=normalized, organization=organization
        ).first()
        if alias:
            return alias
    return CustomFieldAlias.objects.filter(
        normalized_alias=normalized, organization__isnull=True
    ).first()


def _suggest_similar_custom_field(label, organization, threshold=0.9):
    if not label:
        return None
    target = _normalize_header_value(label)
    if not target:
        return None
    qs = CustomField.objects.all()
    if organization:
        qs = qs.filter(jobs__organization=organization).distinct()
    best_field = None
    best_score = 0.0
    for field in qs:
        candidate = _normalize_header_value(field.label)
        if not candidate:
            continue
        score = SequenceMatcher(None, target, candidate).ratio()
        if score > best_score:
            best_score = score
            best_field = field
    if best_score >= threshold:
        return best_field
    return None


def _ensure_custom_field_alias(field, raw_value, normalized, organization, user):
    if not normalized or not raw_value:
        return
    language = "en"
    CustomFieldAlias.objects.get_or_create(
        normalized_alias=normalized,
        organization=organization,
        defaults={
            "field": field,
            "alias": str(raw_value).strip(),
            "language": language,
            "created_by": user,
        },
    )


def _resolve_custom_field(raw_value, organization, user):
    raw = str(raw_value).strip()
    if not raw:
        return None, ""
    normalized = _normalize_header_value(raw)
    alias = _lookup_custom_field_alias(normalized, organization)
    if alias:
        return alias.field, alias.field.label
    if normalized in NON_LDSF_HEADER_ALIASES:
        label = NON_LDSF_HEADER_ALIASES[normalized]
    else:
        label = _translate_custom_field_name(raw)
    field = CustomField.objects.filter(label=label).first()
    if not field:
        field = _suggest_similar_custom_field(label, organization)
    if not field:
        field = CustomField.objects.create(label=label)
    _ensure_custom_field_alias(field, raw, normalized, organization, user)
    return field, field.label


def _resolve_non_ldsf_fields(header_cells, organization, user):
    fields = []
    field_names = []
    for cell in header_cells:
        if not cell.value:
            continue
        field, label = _resolve_custom_field(cell.value, organization, user)
        if field is None:
            continue
        fields.append(field)
        field_names.append(label)
    return fields, field_names


def _translate_header_to_english(value):
    translated = translate_text(value, source="auto", target="en")
    if translated:
        if translated.strip().lower() == str(value).strip().lower():
            return value
        return _englishify_header(translated)
    return _englishify_header(value)




class SampleUploadView(APIView):
    parser_classes = [MultiPartParser, FileUploadParser]
    permission_classes = [SampleUploadPermission]

    def get_job(self, job_id):
        try:
            return Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            raise Http404

    def post(self, request, *args, **kwargs):
        try:
            job = self.get_job(kwargs.get("job_id"))
            samples_file = request.data["samples"]
            wb = openpyxl.load_workbook(samples_file)
            worksheet = wb.worksheets[0]
            header_cells = next(worksheet.iter_rows(max_row=1))
            header_row = [cell.value for cell in header_cells]

            last_sample = Sample.objects.filter(
                Q(version_one=False) & Q(job__organization=request.user.organization)
            ).last()

            if last_sample is not None:
                last_sample_number = int(last_sample.number[-6:])
            else:
                last_sample_number = 0

            samples = []

            barcodes_dir = os.path.join(
                settings.MEDIA_ROOT,
                "jobs/barcodes",
            )

            organization = request.user.organization
            
            # Count the number of non-empty rows
            row_count = sum(1 for row in worksheet.iter_rows(min_row=2) if any(cell.value for cell in row))

            if job.sampling_design == Job.LDSF:
                # Verify columns are correct
                field_names = _map_ldsf_headers(header_cells[10:])
                if len(field_names) != len(LDSF_FIELDS) or Counter(field_names) != Counter(LDSF_FIELDS):
                    return Response(
                        {"msg": "Please ensure you use the defined template (English or French)."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                ldsf_label_map = _build_ldsf_header_label_map(header_cells[10:])
                numeric_fields = {
                    13: "depth_top",
                    14: "depth_bottom",
                    15: "air_dried_wt",
                    16: "coarse_wt",
                }
                for row in worksheet.iter_rows(min_row=2, max_row=row_count + 1):
                    if not any(cell.value for cell in row):
                        continue
                    for col_idx, field_name in numeric_fields.items():
                        cell_value = row[col_idx].value
                        if not _is_number_value(cell_value):
                            label = ldsf_label_map.get(field_name, field_name)
                            return Response(
                                {
                                    "msg": f"Field '{label}' expected a number but got '{cell_value}'."
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )
            else:  # Non LDSF samples
                fields, field_names = _resolve_non_ldsf_fields(
                    header_cells[10:], organization, request.user
                )

                # Ensure unique column names
                if len(field_names) != len(set(field_names)):
                    return Response(
                        {"msg": "Columns are not unique after translation. Please update and retry."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                for field in fields:
                    field.jobs.add(job)

            try:
                Sample.objects.filter(job_id=job.id).delete()
                remove_folder_name(os.path.join(barcodes_dir, str(job.id)))
            except Exception as e:
                print(e)
                pass

            if job.sampling_design == Job.LDSF:
                samples_details = []
                for row in worksheet.iter_rows(min_row=2, max_row=row_count + 1):
                    if not any(cell.value for cell in row):
                        continue  # Skip empty rows

                    row_dict = {
                        "cluster": row[10].value,
                        "plot": row[11].value,
                        "depth_std": row[12].value,
                        "depth_top": row[13].value,
                        "depth_bottom": row[14].value,
                        "air_dried_wt": row[15].value,
                        "coarse_wt": row[16].value,
                    }

                    if row[0].value:  # update existing sample
                        try:
                            sample = Sample.objects.get(number=row[0].value)
                            SampleLDSFDetail.objects.filter(sample=sample).update(
                                **row_dict
                            )
                        except Sample.DoesNotExist:
                            pass  # TODO: log instead of pass
                        continue

                    sample = Sample.objects.create(
                        number=generate_sample_number(
                            last_sample_number + len(samples) + 1,
                            organization=organization,
                        ),
                        job_id=job.id,
                    )
                    samples.append(sample if not sample.version_one else "")
                    details = SampleLDSFDetail(**row_dict, sample=sample)
                    samples_details.append(details)

                SampleLDSFDetail.objects.bulk_create(samples_details)

            else:  # Non LDSF samples
                values = []
                for row in worksheet.iter_rows(min_row=2, max_row=row_count + 1):
                    if not any(cell.value for cell in row):
                        continue  # Skip empty rows

                    sample = Sample.objects.create(
                        number=generate_sample_number(
                            last_sample_number + len(samples) + 1,
                            organization=organization,
                        ),
                        job_id=job.id,
                    )
                    samples.append(sample if not sample.version_one else "")

                    for field, cell in zip(fields, row[10:]):
                        if cell.value:
                            values.append(
                                CustomFieldValue(
                                    field=field, value=cell.value, sample=sample
                                )
                            )

                CustomFieldValue.objects.bulk_create(values)

            if samples:
                job.samples_uploaded_by = request.user
                job.samples_uploaded_at = timezone.now()
                job.save()

                # create barcodes
                create_barcodes(job_id=job.id, samples=samples)

            return Response(
                {
                    "samples_created": len(samples),
                    "samples_uploaded_at": timezone.now(),
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
      
            Sample.objects.filter(job_id=job.id).delete()
            return JsonResponse({"errors": str(e)}, status=400)






# class SampleUploadView(APIView):
#     parser_classes = [MultiPartParser, FileUploadParser]
#     permission_classes = [SampleUploadPermission]

#     def get_job(self, job_id):
#         try:
#             return Job.objects.get(id=job_id)
#         except Job.DoesNotExist:
#             raise Http404

#     def post(self, request, *args, **kwargs):
#         try:
#             job = self.get_job(kwargs.get("job_id"))
#             samples_file = request.data["samples"]
#             wb = openpyxl.load_workbook(samples_file)
#             worksheet = wb.worksheets[0]

#             # last_sample = Sample.objects.filter(Q(number__contains='WA')).last()
#             last_sample = Sample.objects.filter(
#                 Q(version_one=False) & Q(job__organization=request.user.organization)
#             ).last()
#             
#             

#             if last_sample is not None:
#                 last_sample_number = int(last_sample.number[-6:])
#             else:
#                 last_sample_number = 0

#             samples = []

#             barcodes_dir = os.path.join(
#                 settings.MEDIA_ROOT,
#                 "jobs/barcodes",
#             )

#             try:
#                 Sample.objects.filter(job_id=job.id).delete()
#                 remove_folder_name(os.path.join(barcodes_dir, str(job.id)))
#             except Exception as e:
#                 print(e)
#                 pass
#             organization = request.user.organization
#             if job.sampling_design == Job.LDSF:
#                 # verify columns are correct
#                 field_names = []
#                 for row in worksheet.iter_rows(max_row=1):
#                     for cell in row[10:]:
#                         field_names.append(cell.value.lower())
#                 if len(field_names) != len(LDSF_FIELDS) or Counter(
#                     field_names
#                 ) != Counter(LDSF_FIELDS):
#                     return Response(
#                         {"msg": "Please ensure you use the defined template."},
#                         status=status.HTTP_400_BAD_REQUEST,
#                     )

#                 samples_details = []
#                 for row in worksheet.iter_rows(min_row=2):
#                     row_dict = {
#                         "cluster": "",
#                         "plot": "",
#                         "depth_std": "",
#                         "depth_top": "",
#                         "depth_bottom": "",
#                         "air_dried_wt": "",
#                         "coarse_wt": "",
#                     }
#                     for key, cell in zip(row_dict.keys(), row[10:]):
#                         row_dict[key] = cell.value
#                     if row[0].value:  # update
#                         try:
#                             sample = Sample.objects.get(number=row[0].value)
#                             SampleLDSFDetail.objects.filter(sample=sample).update(
#                                 **row_dict
#                             )
#                         except Sample.DoesNotExist:
#                             pass  # TODO log instead of pass
#                         continue
                    
#                     sample = Sample.objects.create(
#                         number=generate_sample_number(
#                             last_sample_number + len(samples) + 1,
#                             organization=organization,
#                         ),
#                         job_id=job.id,
#                     )
#                     
#                     
#                     samples.append(sample if sample.version_one == False else "")
#                     details = SampleLDSFDetail(**row_dict, sample=sample)
#                     samples_details.append(details)

#                 SampleLDSFDetail.objects.bulk_create(samples_details)

#             else:  # Non LDSF samples
#                 values = []
#                 field_names = []
#                 fields = []

#                 # get fields
#                 for row in worksheet.iter_rows(max_row=1):
#                     for cell in row[10:]:
#                         if not cell.value:
#                             break
#                         field_names.append(cell.value)

#                 # ensure unique
#                 if len(field_names) - len(set(field_names)) != 0:
#                     return Response(
#                         {"msg": "Columns are not unique. Please update and retry."},
#                         status=status.HTTP_400_BAD_REQUEST,
#                     )

#                 for field_name in field_names:
#                     field, created = CustomField.objects.get_or_create(label=field_name)
#                     field.jobs.add(job)
#                     fields.append(field)

#                 for row in worksheet.iter_rows(min_row=2):
#                     sample = Sample.objects.create(
#                         number=generate_sample_number(
#                             last_sample_number + len(samples) + 1,
#                             organization=organization,
#                         ),
#                         job_id=job.id,
#                     )
#                     samples.append(sample if sample.version_one == False else "")

#                     for field, cell in zip(fields, row[10:]):
#                         value = cell.value
#                         if not value:
#                             continue
#                         values.append(
#                             CustomFieldValue(field=field, value=value, sample=sample)
#                         )
#                 CustomFieldValue.objects.bulk_create(values)

#             if samples:
#                 job.samples_uploaded_by = request.user
#                 job.samples_uploaded_at = timezone.now()
#                 job.save()

#                 # create barcodes
#                 create_barcodes(job_id=job.id, samples=samples)

#             return Response(
#                 {
#                     "samples_created": len(samples),
#                     "samples_uploaded_at": timezone.now(),
#                 },
#                 status=status.HTTP_201_CREATED,
#             )
#         except Exception as e:
#             Sample.objects.filter(job_id=job.id).delete()
#             return JsonResponse({"errors": str(e)}, status=400)


class SampleTemplateDownloadView(View):
    def get(self, request):
        job_type = request.GET.get("type")
        lang = request.GET.get("lang", "en").lower()
        if job_type not in ("ldsf", "non_ldsf") or lang not in ("en", "fr"):
            raise Http404
        template_name_map = {
            ("ldsf", "en"): "ldsf_samples_template.xlsx",
            ("ldsf", "fr"): "ldsf_samples_template_fr.xlsx",
            ("non_ldsf", "en"): "non_ldsf_samples_template.xlsx",
            ("non_ldsf", "fr"): "non_ldsf_samples_template_fr.xlsx",
        }
        template_name = template_name_map[(job_type, lang)]
        file_path = os.path.join(settings.BASE_DIR, "media", "downloads", template_name)
        with open(file_path, "rb") as df:
            response = HttpResponse(
                df.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f"attachment; filename={template_name}"

            return response


class JobSampleList(ListView):
    template_name = "samples.html"
    context_object_name = "samples"
    # paginate_by = PAGINATION_SIZE

    def dispatch(self, request, *args, **kwargs):
        self.job = get_object_or_404(Job, pk=kwargs["job_id"])
        self.field_mapping = {}  # Initialize field mapping for custom fields
        return super(JobSampleList, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(JobSampleList, self).get_context_data(**kwargs)
        context["job"] = self.job
        # For non-LDSF jobs, use sanitized field names that match the annotated queryset keys
        if self.job.sampling_design != Job.LDSF and self.field_mapping:
            context["fields"] = list(self.field_mapping.keys())  # Sanitized field names
            context["field_labels"] = list(self.field_mapping.values())  # Original labels for display
            context["field_mapping"] = self.field_mapping  # Full mapping for reference
        else:
            context["fields"] = self._get_sample_fields()
        return context

    def get_queryset(self):
        samples = Sample.objects.filter(job_id=self.job.pk)

        if self.job.sampling_design == Job.LDSF:
            return samples.select_related("sampleldsfdetail")

        if samples:
            fields = CustomField.objects.filter(jobs__in=[self.job]).values_list(
                "label", flat=True
            )

            # Create sanitized field names for annotations (replace spaces and special chars with underscores)
            def sanitize_field_name(field_name):
                # Replace whitespace, quotes, semicolons, hashes, and SQL comment markers with underscores
                import re
                sanitized = re.sub(r'[\s"\'#;-]+', '_', field_name)
                # Remove leading/trailing underscores
                sanitized = sanitized.strip('_')
                return sanitized

            # Map sanitized names to original field labels
            self.field_mapping = {sanitize_field_name(field): field for field in fields}

            d = {
                sanitized_field: Subquery(
                    CustomFieldValue.objects.filter(
                        field__label=original_field, sample_id=OuterRef("pk")
                    ).values("value")
                )
                for sanitized_field, original_field in self.field_mapping.items()
            }

            samples = samples.annotate(**d)

            page_obj = samples.values("number", "job", "barcode", "qr_code", *self.field_mapping.keys())
            return page_obj

    def _get_sample_fields(self) -> list:
        if self.job.sampling_design == Job.LDSF:
            return LDSF_FIELDS
        return list(self.job.customfield_set.values_list("label", flat=True))

    def render_to_response(self, context, **response_kwargs):
        if "export" in self.request.GET:
            lang = (self.request.GET.get("lang") or "en").strip().lower()
            if lang.startswith("fr"):
                lang = "fr"
            else:
                lang = "en"

            base_headers_en = [
                "SSN",
                "Job No",
                "Study",
                "Scientist",
                "Site",
                "Region",
                "Country",
                "Material",
                "Sampling",
                "Date",
            ]
            base_headers_fr = [
                "SSN",
                "Numéro de travail",
                "Étude",
                "Scientifique",
                "Site",
                "Région",
                "Pays",
                "Matériel",
                "Échantillonnage",
                "Date",
            ]
            field_label_map_fr = {
                "cluster": "Groupe",
                "plot": "Parcelle",
                "depth_std": "Profondeur_Standard",
                "depth_top": "Profondeur_Supérieure",
                "depth_bottom": "Profondeur_Inférieure",
                "air_dried_wt": "Poids_Séché_Air",
                "coarse_wt": "Poids_Grossier",
            }
            base_headers = base_headers_fr if lang == "fr" else base_headers_en
            # construct header row
            # Use original field labels for headers if available, otherwise use fields
            field_headers = context.get("field_labels", context["fields"])
            if lang == "fr":
                field_headers = [
                    field_label_map_fr.get(str(field).strip(), field)
                    for field in field_headers
                ]
            headers = base_headers + list(field_headers)
            wb = Workbook()
            file_name = f"samples_{self.job.job_number}.xlsx"
            ws1 = wb.active
            ws1.title = "Sample List"

            job = self.job
            country = pycountry.countries.get(alpha_2=job.country).name
            sampling_design = job.get_sampling_design_display()

            non_sample_info = ["number", "job", "barcode", "qr_code"]
            # write header
            for row in range(1):
                ws1.append(headers)

            material_design = []

            # try:?
            if job.plant:
                for key, value in job.plant.items():
                    if int(value) > 0:
                        material_design.append("plant")
            if job.soil:
                for key, value in job.soil.items():
                    if int(value) > 0:
                        material_design.append("soil")
            if job.fertilizer:
                for key, value in job.fertilizer.items():
                    if int(value) > 0:
                        material_design.append("fertilizer")
            if job.other:
                for key, value in job.other.items():
                    if int(value) > 0:
                        material_design.append("other")
            # except Exception as e:
            #     pass

            for i in context["object_list"]:
                if sampling_design.lower() == "ldsf":
                    ws1.append(
                        [
                            i.number,
                            job.job_number,
                            job.project,
                            job.scientist_name,
                            job.site,
                            job.region,
                            country,
                            ",".join(
                                [
                                    str(
                                        item,
                                    )
                                    for item in material_design
                                ]
                            ),
                            sampling_design,
                            "",
                            i.sampleldsfdetail.cluster,
                            i.sampleldsfdetail.plot,
                            i.sampleldsfdetail.depth_std,
                            i.sampleldsfdetail.depth_top,
                            i.sampleldsfdetail.depth_bottom,
                            i.sampleldsfdetail.air_dried_wt,
                            i.sampleldsfdetail.coarse_wt,
                        ]
                    )
                elif sampling_design.lower() == "non-ldsf":
                    table_headers = i.keys()
                    data = [
                        i["number"],
                        job.job_number,
                        job.project,
                        job.scientist_name,
                        job.site,
                        job.region,
                        country,
                        ",".join(
                            [
                                str(
                                    item,
                                )
                                for item in material_design
                            ]
                        ),
                        # "",
                        sampling_design,
                        "",
                    ]

                    # Iterate through sanitized keys (from annotation) but respect field order
                    for key in table_headers:
                        if key not in non_sample_info:
                            data.append(i[key])
                    ws1.append(data)

            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = f"attachment; filename={file_name}"
            wb.save(response)
            return response

        return super(JobSampleList, self).render_to_response(context, **response_kwargs)


class JobTestScheduleList(ListView):
    model = JobTest
    template_name = "jobs_instrument.html"
    context_object_name = "tests"
    paginate_by = PAGINATION_SIZE

    def get_queryset(self):


        user = self.request.user
        user_organization = user.organization
        instrument_id = self.request.GET.get("instrument_id")
        test_id = self.request.GET.get("test_id")

        # if not( user.is_superuser and not instrument.user_has_access(user=user)) or  self.request.user.groups.filter(name=Regional Admin).exists() or  self.request.user.groups.filter(name="Regional Admin").exists():
        #     raise Http404
    

        if  instrument_id != None:
            instrument = get_object_or_404(LabInstrument, pk=instrument_id)
            queryset = (
                JobTest.objects.filter(Q(job__testing_authorized_at__isnull=False) &  Q(test__test__instrument_id=instrument_id ))
                .select_related("job")
                .order_by("-job_id").distinct()
            )
        else:
            queryset = (
                JobTest.objects.filter(Q(job__testing_authorized_at__isnull=False) &  Q(test__test__id=test_id ))
                .select_related("job")
                .order_by("-job_id").distinct()
            )
            

    
        if not self.request.user.groups.filter(name="Regional Admin").exists():
            queryset = queryset.filter(job__organization=user_organization)
            

        # Apply search filter
        search = self.request.GET.get("search")
        if search:
            try:
                country = pycountry.countries.search_fuzzy(search)[0]
                country_code = country.alpha_2
            except LookupError:
                country_code = None

            queryset = queryset.filter(
                Q(job__job_number__icontains=search)
                | Q(job__scientist_name__icontains=search)
                | Q(job__scientist_email__icontains=search)
                | Q(job__sampling_design__icontains=search)
                | Q(job__country=country_code)
                | Q(job__region__icontains=search)
                | Q(job__project__icontains=search)
                | Q(job__site__icontains=search)
            )

        # Apply organization filter
        # organization_id = self.request.GET.get("organization")
        # if organization_id:
        #     queryset = queryset.filter(job__organization_id=organization_id)
        # import pdb
        # pdb.set_trace()

        return queryset

    def get_context_data(self, **kwargs):
     
        context = super().get_context_data(**kwargs)

        # Pagination
        queryset = self.get_queryset()
        paginator = Paginator(queryset, self.paginate_by)
        page_number = self.request.GET.get("page_number", 1)
        page_obj = paginator.get_page(int(page_number))
        

        # Calculate and set the 'adjusted_elided_pages' attribute
        page_obj.adjusted_elided_pages = paginator.get_elided_page_range(
            int(page_number)
        )

        context["tests"] = page_obj

        users = User.objects.filter(organization=self.request.user.organization)
        user_serializer = UserSerializer(users, many=True)

        # Add organizations to context if user is Regional Admin
        if self.request.user.groups.filter(name="Regional Admin").exists():
            organizations = Organization.objects.all()
            context["organizations"] = [
                {
                    "id": org.id,
                    "name": org.name,
                    "country": pycountry.countries.get(alpha_2=org.country).name,
                }
                for org in organizations
            ]

        context["users"] = user_serializer.data
        return context

    def render_to_response(self, context, **response_kwargs):

        if self.request.GET.get("format") == "json":
            data = {
                "results": [self.serialize_job_test(test) for test in context["tests"]],
                "pagination": {
                    "current_page": context["tests"].number,
                    "num_pages": context["tests"].paginator.num_pages,
                    "has_next": context["tests"].has_next(),
                    "has_previous": context["tests"].has_previous(),
                },
            }
            return JsonResponse(data)
        return super().render_to_response(context, **response_kwargs)

    def serialize_job_test(self, job_test):
  
        return {
            "id": job_test.id,
            "job_number": job_test.job.job_number,
            "scientist_name": job_test.job.scientist_name,
            "sampling_design": job_test.job.get_sampling_design_display(),
            "country": job_test.job.country,
            "region": job_test.job.region,
            "project": job_test.job.project,
            "site": job_test.job.site,
            "completion_status": job_test.get_completion_status_display(),
            "start_date": job_test.start_date,
            "end_date": job_test.end_date,
        }




class InstrumentJobList(ListView):
    model = Job
    template_name = "instruments/instrument_jobs.html"
    context_object_name = "jobs"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related(
            Prefetch('job_tests', queryset=JobTest.objects.select_related('test__test__instrument'))
        )
        instrument_id = self.request.GET.get("instrument_id")
        search_query = self.request.GET.get("search")
        organization_id = self.request.GET.get("organization")

        if instrument_id:
            self.instrument = get_object_or_404(LabInstrument, pk=instrument_id)
            job_ids = queryset.filter(
                job_tests__test__test__instrument=self.instrument
            ).values('job_number').annotate(min_id=Min('id')).values_list('min_id', flat=True)
            
            queryset = queryset.filter(id__in=job_ids).order_by('-id')        
    

        # Apply organization filter first
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)

        if search_query:
            search_filter = (
                Q(job_number__icontains=search_query)
                | Q(scientist_name__icontains=search_query)
                | Q(country__icontains=search_query)
                | Q(region__icontains=search_query)
                | Q(project__icontains=search_query)
                | Q(site__icontains=search_query)
                | Q(samples__number__icontains=search_query)
            )

            queryset = queryset.filter(search_filter).distinct()

        return queryset
    
    def get(self, request, *args, **kwargs):
    
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            queryset = self.get_queryset()
         
            paginator = Paginator(queryset, self.paginate_by)
            page = request.GET.get("page", 1)
            jobs = paginator.get_page(page)

            data = {
                "results": [
                    {
                        "id": job.id,
                        "job_number": job.job_number,
                        "scientist_name": job.scientist_name,
                        "sampling_design": job.get_sampling_design_display(),
                        "country": job.country,
                        "region": job.region,
                        "project": job.project,
                        "site": job.site,
                        "data_upload_status": self.get_data_upload_status(job),
                        "organization": (
                            job.organization.name if job.organization else None
                        ),
                    }
                    for job in jobs
                ],
                "current_page": jobs.number,
                "total_pages": jobs.paginator.num_pages,
            }
            return JsonResponse(data)

        return super().get(request, *args, **kwargs)

    def get_data_upload_status(self, job):
        instrument_id = self.request.GET.get("instrument_id")
        if instrument_id:
            job_test = job.job_tests.filter(test__test__instrument_id=instrument_id).first()
            if job_test:
                return job_test.data_upload_status
        return False

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("search", "")
        context["organization_id"] = self.request.GET.get("organization", "")
        context["organizations"] = Organization.objects.all()
        context["instrument"] = getattr(self, "instrument", None)
        context["data_url"] = self.get_data_url()
        qc_reports = {}
        for job in context['jobs']:
            job.data_upload_status = self.get_data_upload_status(job)
            report = getattr(job, "spectra_qc_report", None)
            job.has_qc_report = report is not None and bool(report.summary)
            if job.has_qc_report:
                qc_reports[str(job.id)] = report.summary
        context["job_qc_reports_json"] = json.dumps(qc_reports)
        
        return context

    def get_data_url(self):

        instrument = getattr(self, "instrument", None)
        # import pdb
        # pdb.set_trace()
        
        
        
        if not instrument:
            return reverse("instrument-job-data-files")
        if instrument.opus_output:
            return reverse("instrument-job-data")
        elif instrument.is_wetchemistry == True:
            return reverse("instrument-job-data-files-wetchemistry")
        elif instrument.name.lower() == "xrd":
            return reverse("instrument-job-data-files-xrd")
        elif instrument.opus_output == "Tensor 27 HTS-XT MIR":
            return reverse("instrument-job-data-files-tensor")
        elif instrument.name == "cnO_and_cnT":
            return reverse("instrument-job-data-files-cno-cnt")
        elif instrument.name == "TXRF":
            return reverse("instrument-job-data-files-txrf")
        elif instrument.name == "LDPSA":
            return reverse("instrument-job-data-files-ldpsa")
        elif instrument.is_pxrf == True:
            return reverse("instrument-job-data-files-pxrf")
        elif instrument.is_living_soils == True:
            return reverse("living-soils")
        else:
            return reverse("instrument-job-data-files")


# class InstrumentJobList(ListView):
#     model = Job
#     template_name = "instruments/instrument_jobs.html"
#     context_object_name = "jobs"
#     paginate_by = 10

#     def get_queryset(self):
#         queryset = super().get_queryset()
#         instrument_id = self.request.GET.get("instrument_id")
#         search_query = self.request.GET.get("search")
#         organization_id = self.request.GET.get("organization")

#         if instrument_id:
#             self.instrument = get_object_or_404(LabInstrument, pk=instrument_id)
#             queryset = queryset.filter(job_tests__test__test__instrument=self.instrument)

#         # Apply organization filter first
#         if organization_id:
#             queryset = queryset.filter(organization_id=organization_id)

#         if search_query:
#             search_filter = Q(job_number__icontains=search_query) | \
#                             Q(scientist_name__icontains=search_query) | \
#                             Q(country__icontains=search_query) | \
#                             Q(region__icontains=search_query) | \
#                             Q(project__icontains=search_query) | \
#                             Q(site__icontains=search_query) | \
#                             Q(samples__number__icontains=search_query)

#             queryset = queryset.filter(search_filter).distinct()

#         return queryset

#     def get(self, request, *args, **kwargs):
#         if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#             queryset = self.get_queryset()
#             paginator = Paginator(queryset, self.paginate_by)
#             page = request.GET.get('page', 1)
#             jobs = paginator.get_page(page)

#             data = {
#                 'results': [
#                     {
#                         'id': job.id,
#                         'job_number': job.job_number,
#                         'scientist_name': job.scientist_name,
#                         'sampling_design': job.get_sampling_design_display(),
#                         'country': job.country,
#                         'region': job.region,
#                         'project': job.project,
#                         'site': job.site,
#                         'data_upload_status': job.data_upload_status,
#                         'organization': job.organization.name if job.organization else None,
#                     }
#                     for job in jobs
#                 ],
#                 'current_page': jobs.number,
#                 'total_pages': jobs.paginator.num_pages,
#             }
#             return JsonResponse(data)
#         return super().get(request, *args, **kwargs)

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         # context["instrument"] = self.instrument
#         context["search_query"] = self.request.GET.get("search", "")
#         context["organization_id"] = self.request.GET.get("organization", "")
#         context["organizations"] = Organization.objects.all()
#         return context


#     # def get_queryset(self):
#     #     queryset = super().get_queryset()
#     #     instrument_id = self.request.GET.get("instrument_id")
#     #     search_query = self.request.GET.get("search")
#     #     organization_id = self.request.GET.get("organization")

#     #     if instrument_id:
#     #         self.instrument = get_object_or_404(LabInstrument, pk=instrument_id)
#     #         queryset = queryset.filter(job_tests__test__test__instrument=self.instrument)

#     #     if organization_id:
#     #         queryset = queryset.filter(organization_id=organization_id)

#     #     if search_query:
#     #         queryset = queryset.filter(
#     #             Q(job_number__icontains=search_query) |
#     #             Q(scientist_name__icontains=search_query) |
#     #             Q(country__icontains=search_query) |
#     #             Q(region__icontains=search_query) |
#     #             Q(project__icontains=search_query) |
#     #             Q(site__icontains=search_query) |
#     #             Q(samples__number__icontains=search_query)
#     #         ).distinct()

#     #     return queryset

#     # def get_context_data(self, **kwargs):
#     #     context = super().get_context_data(**kwargs)
#     #     # context["instrument"] = self.instrument
#     #     context["search_query"] = self.request.GET.get("search", "")
#     #     context["organization_id"] = self.request.GET.get("organization", "")
#     #     context["organizations"] = Organization.objects.all()


#         # peint
#         return context


class JobPagination(PageNumberPagination):
    page_size = 10


class JobListAPI(APIView):
    pagination_class = JobPagination

    def get(self, request):
        queryset = Job.objects.all()
        instrument_id = request.GET.get("instrument_id")
        search_query = request.GET.get("search")
        organization_id = request.GET.get("organization")

        if instrument_id:
            queryset = queryset.filter(
                job_tests__test__test__instrument_id=instrument_id
            )

        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)

        if search_query:
            queryset = queryset.filter(
                Q(job_number__icontains=search_query)
                | Q(scientist_name__icontains=search_query)
                | Q(country__icontains=search_query)
                | Q(region__icontains=search_query)
                | Q(project__icontains=search_query)
                | Q(site__icontains=search_query)
                | Q(samples__number__icontains=search_query)
            ).distinct()

        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        data = [
            {
                "id": job.id,
                "job_number": job.job_number,
                "scientist_name": job.scientist_name,
                "country": job.country,
                "region": job.region,
                "project": job.project,
                "site": job.site,
                # Add other fields as needed
            }
            for job in paginated_queryset
        ]

        return Response(
            {
                "results": data,
                "current_page": paginator.page.number,
                "total_pages": paginator.page.paginator.num_pages,
            }
        )


# class InstrumentJobList(ListView):
#     model = Job
#     template_name = "instruments/instrument_jobs.html"
#     context_object_name = "jobs"

#     # paginate_by = PAGINATION_SIZE
#     # pagination_class = CustomPagination
#     def dispatch(self, request, *args, **kwargs):
#         instrument_id = request.GET.get("instrument_id")

#         self.instrument = get_object_or_404(LabInstrument, pk=instrument_id)
#         return super(InstrumentJobList, self).dispatch(request, args, **kwargs)

#     def get_context_data(self, *, object_list=None, **kwargs):
#         context = super(InstrumentJobList, self).get_context_data(**kwargs)
#         context["instrument"] = self.instrument
#         context["paginator"] = CustomPagination()

#         if self.instrument.opus_output:
#             context["data_url"] = reverse("instrument-job-data")
#         elif self.instrument.name == "Wet Chem Reference Analysis":
#             context["data_url"] = reverse("instrument-job-data-files-wetchemistry")
#         elif self.instrument.name.lower() == "xrd":
#             context["data_url"] = reverse("instrument-job-data-files-xrd")
#         elif self.instrument.name == "Tensor 27 HTS-XT MIR":
#             context["data_url"] = reverse("instrument-job-data-files-tensor")
#         elif self.instrument.name == "cnO_and_cnT":
#             context["data_url"] = reverse("instrument-job-data-files-cno-cnt")
#         elif self.instrument.name == "TXRF":
#             context["data_url"] = reverse("instrument-job-data-files-txrf")
#         elif self.instrument.name == "LDPSA":
#             context["data_url"] = reverse("instrument-job-data-files-ldpsa")
#         elif self.instrument.name == "pXRF":
#             context["data_url"] = reverse("instrument-job-data-files-pxrf")
#         elif self.instrument.is_living_soils == True:
#             context["data_url"] = reverse("living-soils")
#         else:
#             context["data_url"] = reverse("instrument-job-data-files")

#         return context

#     def get_queryset(self):
#         jobs = []
#         alpha_instrument = LabInstrument.objects.filter(name="Alpha ZnSe_FTMIR_Alpha_I")

#         job_test = (
#             JobTest.objects.all()
#             .distinct("job_id")
#             .filter(test__test__instrument=self.instrument)
#             .order_by("-job_id")
#         )

#         pxrf_test = (
#             JobTest.objects.all().filter(Q(test=50) | Q(test=87)).order_by("-job_id")
#         )

#         # is_completed_objects = IsCompletedDataUpload.objects.filter(test__name=self.instrument)

#         # for is_completed_object in is_completed_objects:
#         #     completion_status[is_completed_object] = is_completed_object
#         if self.instrument.name == "Alpha ZnSe_FTMIR_Alpha_I":
#             for id in job_test:
#                 jobs.append(Job.objects.filter(id=id.job_id))
#             page_obj = job_test
#             # return page_obj
#         elif self.instrument.name == "Alpha ZnSe_FTMIR_Alpha_II":
#             for id in job_test:
#                 jobs.append(Job.objects.filter(id=id.job_id))
#             page_obj = job_test
#             # return page_obj
#         elif self.instrument.name == "Wet Chem Reference Analysis":
#             for id in job_test:
#                 jobs.append(Job.objects.filter(id=id.job_id))
#             page_obj = job_test
#             # return page_obj
#         elif self.instrument.name == "cnO_and_cnT":
#             for id in job_test:
#                 jobs.append(Job.objects.filter(id=id.job_id))
#             page_obj = job_test
#             # return page_obj

#         elif self.instrument.name == "pXRF Version 1":
#             for id in pxrf_test:
#                 jobs.append(Job.objects.filter(id=id.job_id))
#             page_obj = pxrf_test
#             # return page_obj
#         page_obj = job_test

#         # Create an instance of your custom pagination class
#         custom_pagination = CustomPagination()
#         custom_pagination.page_size = PAGINATION_SIZE  # Set your desired page size here
#         # Create a paginator using your custom pagination
#         paginator = Paginator(page_obj, custom_pagination.page_size)
#         page_number = self.request.GET.get("page_number")

#         if page_number == None:
#             page_number = 1
#         page_obj = paginator.get_page(int(page_number))

#         # Calculate and set the 'adjusted_elided_pages' attribute
#         page_obj.adjusted_elided_pages = paginator.get_elided_page_range(
#             int(page_number)
#         )
#         return page_obj


def update_pxrf_instrument(self):
    job_tests = JobTest.objects.filter(
        Q(test__instrument__name="pXRF") & Q(job__job_number__icontains="2014")
        | Q(job__job_number__icontains="2015")
        | Q(job__job_number__icontains="2016")
        | Q(job__job_number__icontains="2017")
        | Q(job__job_number__icontains="2018")
        | Q(job__job_number__icontains="2019")
        | Q(job__job_number__icontains="2020")
    )

    pxrfs = job_tests.filter(test__instrument__name="pXRF")

    pxrf_v2 = LabTest.objects.get(id=37)

    for pxrf in pxrfs:
        pxrf.test = pxrf_v2
        pxrf.save()
    return HttpResponse("updated")


class BarcodeList(ListView):
    context_object_name = "images"

    def __init__(self, **kwargs):
        self.barcodes_only = True
        super().__init__(**kwargs)

    def dispatch(self, request, *args, **kwargs):
        self.barcodes_only = "recording_sheet" not in request.GET
        return super(BarcodeList, self).dispatch(request, *args, **kwargs)

    def get_template_names(self):
        if self.barcodes_only:
            return "print_barcodes.html"
        return "recording_sheet.html"

    def extract_digits(self, string_value):
        """
        Extract only the numeric part from a string.
        
        Args:
            string_value (str): The string containing numbers and other characters
            
        Returns:
            str: Only the digits from the string
        """
        return ''.join(char for char in string_value if char.isdigit())

    def get_context_data(self, **kwargs):
        context = super(BarcodeList, self).get_context_data(**kwargs)
        job_id = self.kwargs["pk"]
        barcodes_type = self.request.GET.get("type")
        job = get_object_or_404(Job, pk=job_id)
        lang = (self.request.GET.get("lang") or "en").strip().lower()
        if lang.startswith("fr"):
            lang = "fr"
        else:
            lang = "en"
        labels = {
            "en": {
                "title": "Sample Recording Sheet",
                "job": "Job #",
                "site": "Site",
                "scientist": "Scientist",
                "cup_number": "Cup Number",
                "ssn": "SSN",
                "qr_code": "QR Code",
                "scanned": "Scanned",
                "language": "Language",
                "english": "English",
                "french": "Francais",
            },
            "fr": {
                "title": "Feuille d'enregistrement des echantillons",
                "job": "Travail #",
                "site": "Site",
                "scientist": "Scientifique",
                "cup_number": "Numero de coupelle",
                "ssn": "SSN",
                "qr_code": "Code QR",
                "scanned": "Scanne",
                "language": "Langue",
                "english": "Anglais",
                "french": "Francais",
            },
        }
        params_en = self.request.GET.copy()
        params_en["lang"] = "en"
        params_fr = self.request.GET.copy()
        params_fr["lang"] = "fr"
        context["title"] = f"{job.job_number}_{barcodes_type}"
        context["type"] = barcodes_type
        context["job"] = job
        context["lang"] = lang
        context["labels"] = labels[lang]
        context["lang_url_en"] = f"?{params_en.urlencode()}"
        context["lang_url_fr"] = f"?{params_fr.urlencode()}"
        return context

    def get_queryset(self):
        barcode_type = self.request.GET.get("type")
        if barcode_type not in ("barcode", "qr_code"):
            raise Http404
        # if self.barcodes_only:
        #     return Sample.objects.filter(job_id=self.kwargs["pk"]).values(
        #         "number", barcode_type
        #     )
        # return Sample.objects.filter(job_id=self.kwargs["pk"]).values(
        #     "number", barcode_type
        # )
        samples = Sample.objects.filter(job_id=self.kwargs["pk"])
        result = []
        for sample in samples:
            sample_data = {
                "number": sample.number,
                "number_digits": self.extract_digits(sample.number),
                barcode_type: getattr(sample, barcode_type)
            }
            result.append(sample_data)
        
        return result


class NewJobTemplateView(TemplateView):
    template_name = "new_job.html"


class InstrumentDataTemplateVersionOne(ListView):
    model = LabInstrument
    template_name = "instruments/instrument_select_data_version_one.html"

    def get_queryset(self):
        user = self.request.user
        return (
            {
                "version_1": user.labinstrument_set.all()
                .filter(is_active=False)
                .filter(is_living_soils=False),
            }
            if not user.is_superuser
            else {
                "version_1": LabInstrument.objects.filter(is_active=False).filter(
                    is_living_soils=False
                ),
            }
        )


class InstrumentDataTemplateVersionTwo(ListView):
    model = LabInstrument
    template_name = "instruments/instrument_select_data_version_two.html"

    def get_queryset(self):
        user = self.request.user

        # Define base queryset filters that apply to all queries
        base_filters = {"is_active": True}

        # if not user.is_superuser:
        #     # For non-superusers, filter instruments related to the user
        #     queryset = user.labinstrument_set.filter(**base_filters)
        # else:
        # For Regional Admins
        if self.request.user.groups.filter(name="Regional Admin").exists():
            # For ICRAF Kenya superusers, show instruments from both ICRAF and CIFOR
            queryset = LabInstrument.objects.filter(**base_filters)
        elif self.request.user.groups.filter(name="Regional Admin").exists():
            # For other superusers, show only instruments from their organization
            queryset = LabInstrument.objects.filter(
                **base_filters, organization=user.organization
            )
        else:
            queryset = user.labinstrument_set.filter(**base_filters)
        
        

        # Filter queryset for version 2 and living soils
        version_2_queryset = queryset.filter(
            Q(all_jobs=False) & Q(is_living_soils=False)
        ).exclude(name='Sample processing packages')
        living_soils_queryset = queryset.filter(is_living_soils=True)

        return {
            "version_2": version_2_queryset,
            "living_soils": living_soils_queryset,
            "user_organization": user.organization.name,
            "user_country": user.organization.country,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        # Group version 2 instruments by organization
        version_2_grouped = self.group_by_organization(queryset["version_2"])

        # Group living soils instruments by organization
        living_soils_grouped = self.group_by_organization(queryset["living_soils"])

        context.update(
            {
                "version_2_grouped": version_2_grouped,
                "living_soils_grouped": living_soils_grouped,
                "user_organization": queryset["user_organization"],
                "user_country": queryset["user_country"],
            }
        )
        return context


    def group_by_organization(self, queryset):
        sorted_queryset = sorted(
        queryset,
        key=lambda x: (
            x.organization.name if x.organization else "",
            x.organization.country if x.organization else ""
            )
        )

        # Group the sorted queryset by organization name and country
        grouped = {}
        for (org_name, org_country), instruments in groupby(
            sorted_queryset,
            key=lambda x: (
                x.organization.name if x.organization else "No Organization",
                x.organization.country if x.organization else "No Country"
            ),
        ):
            
            org_key = f"{org_name} ({pycountry.countries.get(alpha_2=org_country).name})"
            grouped[org_key] = list(instruments)

        return grouped



def download_file(request, filename=""):
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = DataUpload.objects.filter(uploaded_file__icontains=filename)
        filepath = BASE_DIR + "/" + "media" + "/" + file_path[0].uploaded_file.name
        template_name = filename

        with open(filepath, "rb") as df:
            response = HttpResponse(
                df.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f"attachment; filename={template_name}"

        return response
    except Exception as e:
        return e


def download_pxrf_file(request, filename="", job=""):
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = (
            BASE_DIR
            + "/"
            + "media"
            + "/"
            + "jobs/data/pXRF/"
            + str(job)
            + "/"
            + filename
        )
        template_name = filename

        with open(filepath, "rb") as df:
            response = HttpResponse(
                df.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f"attachment; filename={template_name}"

        return response
    except Exception as e:
        return e


def download_living_soils_images(request, filename=""):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    job = Job.objects.get(job_number=filename)
    file_path = DataUpload.objects.filter(job_id=job.id).exclude(
        uploaded_file__icontains="xlsx"
    )
    filepath = BASE_DIR + "/" + "media" + "/" + file_path[0].uploaded_file.name
    wrapper = FileWrapper(open(filepath, "rb"))
    content_type = mimetypes.guess_type(filepath)[0]
    response = HttpResponse(wrapper)
    response["Content-Disposition"] = "attachment; filename=%s" % filepath
    return response


def download_xrd_folders(request, filename=""):
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = BASE_DIR + "/media/jobs/zip/xrd/" + str(filename)
        job = Job.objects.get(id=filepath.split("/")[-1])
        for filenames in os.walk(filepath):
            zipped_file = filepath + "/" + filenames[2][0]
            response = HttpResponse(
                open(zipped_file, "rb"), content_type="application/zip"
            )
            response["Content-Disposition"] = "attachment; filename={}-XRD".format(
                job.job_number
            )
        return response
    except Exception as e:
        return e
import os
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.views.generic import ListView
from django.http import Http404
from .models import Job, LabInstrument, DataUpload, WetChemSampleData, WetChemColumn, WetChemValue, WetChemBridge

class InstrumentJobDataFilesWetChemistry(ListView):
    model = DataUpload
    template_name = "instruments/instrument_job_data_files_wet.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.request.GET.get("job_id")
        instrument_id = self.request.GET.get("instrument_id")
        if job_id is None or instrument_id is None:
            raise Http404
        self.job = get_object_or_404(Job, pk=int(job_id))
        self.instrument = get_object_or_404(LabInstrument, pk=int(instrument_id))
        return super(InstrumentJobDataFilesWetChemistry, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(InstrumentJobDataFilesWetChemistry, self).get_context_data(
            **kwargs
        )
        context["instrument"] = self.instrument
        context["job"] = self.job
        return context

    def get_queryset(self):
        try:
            wetchem_files_dir = os.path.join(
                settings.MEDIA_ROOT,
                "jobs/data/wetchemistry",
            )
            raw_data_files = {}
            full_path = os.path.join(wetchem_files_dir, str(self.job.id))
            for path in os.listdir(full_path):
                if "csv" not in path:
                    raw_file = os.path.join(full_path, path)
                    raw_data_files[raw_file] = path

            # Get standard WetChemSampleData
            wetchem_compiled_data = list(WetChemSampleData.objects.filter(
                job=self.job
            ).values())

            # Get additional columns and their values
            additional_columns = WetChemColumn.objects.all()
            for sample_data in wetchem_compiled_data:
                ssn = sample_data['ssn']
                for column in additional_columns:
                    try:
                        value = WetChemValue.objects.get(
                            job=self.job,
                            ssn=ssn,
                            wetchembridge__column=column
                        )
                        sample_data[column.name] = value.value
                    except WetChemValue.DoesNotExist:
                        sample_data[column.name] = None
                        
            print()

            data = {
                "raw_files": raw_data_files,
                "wetchem_data": wetchem_compiled_data,
                "job_number": self.job.job_number,
                "is_completed": 0,
            }

            return data
        except Exception as e:
            print(e)
            return "empty"

# class InstrumentJobDataFilesWetChemistry(ListView):
#     model = DataUpload
#     template_name = "instruments/instrument_job_data_files_wet.html"

#     def dispatch(self, request, *args, **kwargs):
#         job_id = self.request.GET.get("job_id")
#         instrument_id = self.request.GET.get("instrument_id")
#         if job_id is None or instrument_id is None:
#             raise Http404
#         self.job = get_object_or_404(Job, pk=int(job_id))
#         self.instrument = get_object_or_404(LabInstrument, pk=int(instrument_id))
#         return super(InstrumentJobDataFilesWetChemistry, self).dispatch(
#             request, *args, **kwargs
#         )

#     def get_context_data(self, *, object_list=None, **kwargs):
#         context = super(InstrumentJobDataFilesWetChemistry, self).get_context_data(
#             **kwargs
#         )
#         context["instrument"] = self.instrument
#         context["job"] = self.job
#         return context

#     def get_queryset(self):
#         try:
#             wetchem_files_dir = os.path.join(
#                 settings.MEDIA_ROOT,
#                 "jobs/data/wetchemistry",
#             )
#             raw_data_files = {}
#             full_path = os.path.join(wetchem_files_dir, str(self.job.id))
#             for path in os.listdir(full_path):
#                 if "csv" not in path:
#                     raw_file = os.path.join(full_path, path)
#                     raw_data_files[raw_file] = path

#             wetchem_compiled_data = WetChemSampleData.objects.filter(
#                 job=self.job
#             ).values()
            

#             data = {
#                 "raw_files": raw_data_files,
#                 "wetchem_data": wetchem_compiled_data,
#                 "job_number": self.job.job_number,
#                 "is_completed": 0,
#             }

#             return data
#         except Exception as e:
#             print(e)
#             return "empty"






class InstrumentJobDataFilesWetChemistry(ListView):
    model = DataUpload
    template_name = "instruments/instrument_job_data_files_wet.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.request.GET.get("job_id")
        instrument_id = self.request.GET.get("instrument_id")
        if job_id is None or instrument_id is None:
            raise Http404
        self.job = get_object_or_404(Job, pk=int(job_id))
        self.instrument = get_object_or_404(LabInstrument, pk=int(instrument_id))
        return super(InstrumentJobDataFilesWetChemistry, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(InstrumentJobDataFilesWetChemistry, self).get_context_data(
            **kwargs
        )
        context["instrument"] = self.instrument
        context["job"] = self.job
        return context


    def get_queryset(self):
        try:
            wetchem_files_dir = os.path.join(
                settings.MEDIA_ROOT,
                "jobs/data/wetchemistry",
            )
            raw_data_files = {}
            full_path = os.path.join(wetchem_files_dir, str(self.job.id))
            for path in os.listdir(full_path):
                if "csv" not in path:
                    raw_file = os.path.join(full_path, path)
                    raw_data_files[raw_file] = path

            # Get all standard columns from WetChemSampleData
            standard_columns = [field.name for field in WetChemSampleData._meta.get_fields() 
                                if not field.is_relation]

            # Get all additional columns
            additional_columns = list(WetChemColumn.objects.values_list('name', flat=True))

            # Combine all column names
            all_columns = standard_columns + additional_columns

            # Get standard WetChemSampleData
            wetchem_data = WetChemSampleData.objects.filter(job=self.job)

            # Get additional data
            additional_data = WetChemValue.objects.filter(job=self.job).prefetch_related(
                Prefetch('wetchembridge_set', queryset=WetChemBridge.objects.select_related('column'))
            )

            wetchem_compiled_data = []
            for sample in wetchem_data:
                sample_data = {field: getattr(sample, field) for field in standard_columns}
                
                # Add additional columns data
                for value in additional_data.filter(ssn=sample.ssn):
                    for bridge in value.wetchembridge_set.all():
                        column_name = bridge.column.name
                        sample_data[column_name] = value.value

                wetchem_compiled_data.append(sample_data)

            data = {
                "raw_files": raw_data_files,
                "wetchem_data": wetchem_compiled_data,
                "columns": all_columns,
                "job_number": self.job.job_number,
                "is_completed": 0,
            }

            return data
        except Exception as e:
            print(e)
            return "empty"
class InstrumentJobDataFilespXRF(ListView):
    model = DataUpload
    template_name = "instruments/instrument_job_data_files_pxrf.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.request.GET.get("job_id")
        instrument_id = self.request.GET.get("instrument_id")
        if job_id is None or instrument_id is None:
            raise Http404
        self.job = get_object_or_404(Job, pk=int(job_id))
        self.instrument = get_object_or_404(LabInstrument, pk=int(instrument_id))
        return super(InstrumentJobDataFilespXRF, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(InstrumentJobDataFilespXRF, self).get_context_data(**kwargs)
        context["instrument"] = self.instrument
        context["job"] = self.job
        return context

    def get_queryset(self):
        try:
            pxrf_files_dir = os.path.join(
                settings.MEDIA_ROOT,
                "jobs/data/pXRF",
            )
            raw_data_files = {}
            files = []
            full_path = os.path.join(pxrf_files_dir, str(self.job.id))
            for path in os.listdir(full_path):
                if "csv" in path:
                    files.append(path)
                    raw_data_files[path] = os.path.join(
                        settings.MEDIA_ROOT, "jobs/data/pXRF", str(self.job.id), path
                    )
                if "xlsx" in path:
                    raw_data_files[path] = os.path.join(
                        settings.MEDIA_ROOT, "jobs/data/pXRF", str(self.job.id), path
                    )

            data = {
                # "headers": headers,
                # "rows": out,
                "job": self.job,
                "files": raw_data_files,
            }

            return data
        except Exception as e:
            print(e)
            return "empty"


class InstrumentJobDataFilesLDPSA(ListView):
    model = DataUpload
    template_name = "instruments/instrument_job_data_files_ldpsa.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.request.GET.get("job_id")
        instrument_id = self.request.GET.get("instrument_id")
        if job_id is None or instrument_id is None:
            raise Http404
        self.job = get_object_or_404(Job, pk=int(job_id))
        self.instrument = get_object_or_404(LabInstrument, pk=int(instrument_id))
        return super(InstrumentJobDataFilesLDPSA, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(InstrumentJobDataFilesLDPSA, self).get_context_data(**kwargs)
        context["instrument"] = self.instrument
        context["job"] = self.job
        return context

    def get_queryset(self):
        excel_files = DataUpload.objects.filter(
            job=self.job, instrument=self.instrument
        )
        if len(excel_files) > 0:
            show_download = True
        try:
            ldpsa_files_dir = os.path.join(
                settings.MEDIA_ROOT, "jobs/data/{}".format(self.instrument.name)
            )
            for excel_file in excel_files:
                file_name = excel_file.uploaded_file.name
                if "frequency" in excel_file.uploaded_file.name:
                    file_path = os.path.join(settings.MEDIA_ROOT, file_name)
                    df = pd.read_excel(file_path, header=0)
                    df_headers = df.head(0)

                    frame = pd.read_excel(file_path)
                    frame.fillna("-", inplace=True)

                else:
                    other_data_files = {}
                    other_file_path = os.path.join(ldpsa_files_dir, str(self.job.id))

                    for path in os.listdir(other_file_path):
                        if "frequency" not in path:
                            raw_file = os.path.join(other_file_path, path)
                            other_data_files[raw_file] = path
                        elif "frequency" in path:
                            view_table_name = path

            headers = []

            for header in df_headers:
                headers.append(header)

            data = []  # Initialize an empty list to hold your data rows

            # Populate the data list with rows from your DataFrame
            for row in frame.iterrows():
                data.append(row)

            data_dict = {
                "headers": headers,
                "data": data,
                "other_excel_file": other_data_files,
                "job_number": self.job.job_number,
                "title_table_data": view_table_name,
            }

            return data_dict

        except Exception as e:
            dataA = {"error": str(e)}
            return dataA


class InstrumentJobDataFilesTxrf(ListView):
    model = DataUpload
    template_name = "instruments/instrument_job_data_files_txrf.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.request.GET.get("job_id")
        instrument_id = self.request.GET.get("instrument_id")
        if job_id is None or instrument_id is None:
            raise Http404
        self.job = get_object_or_404(Job, pk=int(job_id))
        self.instrument = get_object_or_404(LabInstrument, pk=int(instrument_id))
        return super(InstrumentJobDataFilesTxrf, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(InstrumentJobDataFilesTxrf, self).get_context_data(**kwargs)
        context["instrument"] = self.instrument
        context["job"] = self.job
        return context

    def get_queryset(self):
        csv_sheet = DataUpload.objects.filter(
            job=self.job, instrument=self.instrument, uploaded_file__icontains="csv"
        )
        if len(csv_sheet) > 0:
            show_download = True
        try:
            file_name = csv_sheet[0].uploaded_file.name
            file_path = os.path.join(settings.MEDIA_ROOT, file_name)

            df = pd.read_csv(file_path, skiprows=0)

            headers = []

            for d in pd.read_csv(file_path, nrows=0).columns:
                headers.append(d)

            data = [row for row in df.iterrows()]

            data = {
                "headers": headers,
                "data": df,
                "job_number": self.job.job_number,
            }

        except Exception:
            data = {"error": "No data to view"}
        return data


class InstrumentJobDataFilesCnoCnt(ListView):
    model = DataUpload
    template_name = "instruments/instrument_job_data_files_cno_cnt.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.request.GET.get("job_id")
        instrument_id = self.request.GET.get("instrument_id")
        if job_id is None or instrument_id is None:
            raise Http404
        self.job = get_object_or_404(Job, pk=int(job_id))
        self.instrument = get_object_or_404(LabInstrument, pk=int(instrument_id))
        return super(InstrumentJobDataFilesCnoCnt, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(InstrumentJobDataFilesCnoCnt, self).get_context_data(**kwargs)
        context["instrument"] = self.instrument
        context["job"] = self.job
        return context

    def get_queryset(self):
        csv_sheet = DataUpload.objects.filter(
            job=self.job, instrument=self.instrument, uploaded_file__icontains="csv"
        )
        if len(csv_sheet) > 0:
            show_download = True
        try:
            file_name = csv_sheet[0].uploaded_file.name
            file_path = os.path.join(settings.MEDIA_ROOT, file_name)

            df = pd.read_csv(file_path, skiprows=0)

            headers = []

            for d in pd.read_csv(file_path, nrows=0).columns:
                headers.append(d)

            data = [row for row in df.iterrows()]

            data = {
                "headers": headers,
                "data": df,
                "job_number": self.job.job_number,
            }

        except Exception:
            data = {"error": "No data to view"}
        return data


class InstrumentJobDataFiles(ListView):
    model = DataUpload
    template_name = "instruments/instrument_job_data_files.html"

    def dispatch(self, request, *args, **kwargs):
        
        job_id = self.request.GET.get("job_id")
        instrument_id = self.request.GET.get("instrument_id")
        if job_id is None or instrument_id is None:
            raise Http404
        self.job = get_object_or_404(Job, pk=int(job_id))
        
        self.instrument = get_object_or_404(LabInstrument, pk=int(instrument_id))
        return super(InstrumentJobDataFiles, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, *, object_list=None, **kwargs):
        
        context = super(InstrumentJobDataFiles, self).get_context_data(**kwargs)
        context["instrument"] = self.instrument
        context["job"] = self.job
        return context

    def get_queryset(self):
        
        csv_sheet = DataUpload.objects.filter(
            job=self.job, instrument=self.instrument, uploaded_file__icontains="xlsx"
        )
        if len(csv_sheet) > 0:
            show_download = True
        try:
            file_name = csv_sheet[0].uploaded_file.name

            wb = load_workbook(os.path.join(settings.MEDIA_ROOT, file_name))

            if len(wb.sheetnames) > 1:
                data = {
                    "error": "The excel file uploaded should only contain one worksheet. \
                    Kindly re-upload one with one worksheet under the same file name"
                }
            else:
                worksheet = wb.worksheets[0]
                # getting a particular sheet by name out of many sheets

                excel_data = list()
                # iterating over the rows and
                # getting value from each cell in row
                for row in worksheet.iter_rows():
                    row_data = list()
                    for cell in row:
                        row_data.append(str(cell.value))
                    excel_data.append(row_data)

                data = {
                    "headers": excel_data[0],
                    "data": excel_data[1:],
                    "show_download": show_download,
                    "job_number": self.job.job_number,
                }
        except Exception:
            data = {"error": "No data to view"}
        return data


class InstrumentJobDataLivingSoils(ListView):
    model = DataUpload
    template_name = "instruments/instrument_job_data_files_living_soils.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.request.GET.get("job_id")
        instrument_id = self.request.GET.get("instrument_id")
        if job_id is None or instrument_id is None:
            raise Http404
        self.job = get_object_or_404(Job, pk=int(job_id))
        self.instrument = get_object_or_404(LabInstrument, pk=int(instrument_id))
        return super(InstrumentJobDataLivingSoils, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(InstrumentJobDataLivingSoils, self).get_context_data(**kwargs)
        context["instrument"] = self.instrument
        context["job"] = self.job
        return context

    def get_queryset(self):
        images = LivingSoilsImagesModel.objects.filter(job_id=self.job.id)
        file = os.path.join(
            os.path.join(
                settings.BASE_DIR,
                "media/",
                "jobs",
                "data",
                "living_soils",
                self.instrument.name.lower().replace(" ", "_"),
                str(self.job.id),
            )
        )
        # list to store files

        dir_path = os.path.abspath(os.path.join("media", file))
        res = []

        excel_file_names = []
        image_file_names = []

        for dirpath, dirnames, filenames in walk(dir_path):
            for file in filenames:
                if "xlsx" in file:
                    excel_file_names.append(file)
                else:
                    image_file_names.append(file)

        # Iterate directory
        try:
            for path in os.listdir(dir_path):
                if os.path.isfile(os.path.join(dir_path, path)):
                    if "xlsx" in path:
                        res.append({"analysis": path})
                    else:
                        res.append({"images": path})
        except Exception as e:
            print(str(e), "errroooooorrrrr")

        data = {
            "job_number": self.job.job_number,
            "sampling_design": self.job.sampling_design,
            "region": self.job.region,
            "project": self.job.project,
            "site": self.job.site,
            "scientist_name": self.job.scientist_name,
            "excel": excel_file_names,
            "image": image_file_names,
            # "files": "dsa"
        }
        # except Exception as e:
        #     data = {"error": "No data to view"}

        return data




class InstrumentJobDataTemplate(ListView):
    model = SampleData
    template_name = "instruments/instrument_job_data.html"
    paginate_by = 120

    def get(self, request, *args, **kwargs):
        download_format = self.request.GET.get("format")
        # import pdb
        # pdb.set_trace()
        
        if download_format == "csv":
            job_id = request.GET.get("job_id")
            instrument_id = request.GET.get("instrument_id")

            if not job_id or not instrument_id:
                # Handle the case where job_id or instrument_id is not provided
                return HttpResponse("Job ID or Instrument ID not provided.", status=400)

            try:
                instrument = LabInstrument.objects.get(id=instrument_id)
                job = Job.objects.get(id=job_id)
            except LabInstrument.DoesNotExist:
                return HttpResponse("Instrument not found.", status=404)
            except Job.DoesNotExist:
                return HttpResponse("Job not found.", status=404)

            # Call a method similar to your existing get_queryset logic
            queryset = self.get_queryset()

            # Define your CSV headers
            headers = [
                "SSN",
                "Lab",
                "Plot",
                "Cluster",
                "Material",
                "Instrument",
                "Scan_date",
                "Time",
                "Zone",
                "Duration",
                "Operator",
                "Resolution",
                "Zero_filling_Factor",
                "Number_points",
                "Laser_Wavenumber",
                "Wavenumber_one",
                "Wavenumber_last",
                "Min_absorbance",
                "Max_Absorbance",
                # Add all the other headers you need
            ]

            # Create the HttpResponse object with the appropriate CSV header.
            response = HttpResponse(
                content_type="text/csv",
                headers={
                    "Content-Disposition": 'attachment; filename="sample_data.csv"'
                },
            )

            writer = csv.writer(response)
            data = queryset.values()
            headers += reversed(data[0]["other_data"].keys())
            writer.writerow(headers)  # Write the header

            for obj in queryset:
                # Assuming obj is your model instance with attributes matching the headers
                row = [
                    getattr(obj, "ssn", ""),
                    getattr(obj, "lab", ""),
                    getattr(getattr(obj, "ssn.sampleldsfdetail", obj), "plot", ""),
                    getattr(getattr(obj, "ssn.sampleldsfdetail", obj), "cluster", ""),
                    getattr(obj, "material", ""),
                    getattr(obj, "instrument", ""),
                    getattr(obj, "scan_date", ""),
                    getattr(obj, "time", ""),
                    getattr(obj, "zone", ""),
                    getattr(obj, "duration", ""),
                    getattr(obj, "operator", ""),
                    getattr(obj, "resolution", ""),
                    getattr(obj, "zero_filling_factor", ""),
                    getattr(obj, "number_points", ""),
                    getattr(obj, "laser_wavenumber", ""),
                    getattr(obj, "wavenumber_one", ""),
                    getattr(obj, "wavenumber_last", ""),
                    getattr(obj, "min_absorbance", ""),
                    getattr(obj, "max_absorbance", ""),
                    # Add all the other attributes
                ]
                row.extend(list(obj.other_data.values())[::-1])

                writer.writerow(row)

         
            return response
        return super(InstrumentJobDataTemplate, self).get(
            self, request, *args, **kwargs
        )

    def get_queryset(self):
        
        job_id = self.request.GET.get("job_id")

        instrument_id = self.request.GET.get("instrument_id")
        
        

        instrument = LabInstrument.objects.get(id=instrument_id)
        ins_opus_files_version_one = [
            "MPA_FTNIR_1",
            "Tensor 27 HTS-XT MIR",
            "Alpha ZnSe_1",
            "Alpha KBr",
        ]

        job = Job.objects.get(id=job_id)
        
        
        
        if 'Invenio-S' in instrument.name or 'Invenio_S' in instrument.name:
            if job_id is not None and instrument_id is not None:
                if job.sampling_design == 1:
                    samples_dd_with_custom_field_values = (
                        SampleData.objects.filter(ssn__job_id=job_id)
                        .filter(Q(instrument__icontains="Invenio-S"))
                        .prefetch_related("ssn__sample_custom_field_value")
                    )

                    for sample_data in samples_dd_with_custom_field_values:
                        custom_field_values = (
                            sample_data.ssn.sample_custom_field_value.all()
                        )
                        for custom_field_value in custom_field_values:
                            if custom_field_value.field.label == "Plot":
                                sample_data.plot = custom_field_value.value
                            if custom_field_value.field.label == "Cluster":
                                sample_data.cluster = custom_field_value.value

                    return samples_dd_with_custom_field_values
                else:
                    samples = (
                        SampleData.objects.filter(ssn__job_id=job_id)
                        .filter(Q(instrument__icontains="Invenio-S"))
                        .select_related("ssn__sampleldsfdetail")
                    )
                    return samples

            else:
                return None
            
        # if 'Alpha I' in instrument.name or 'Alpha_I' in instrument.name or 'Alpha I ' in instrument.name:
        #     if job_id is not None and instrument_id is not None:
        #         if job.sampling_design == 1:
        #             samples_dd_with_custom_field_values = (
        #                 SampleData.objects.filter(ssn__job_id=job_id)
        #                 .filter(Q(instrument__icontains="Alpha I"))
        #                 .prefetch_related("ssn__sample_custom_field_value")
        #             )

        #             for sample_data in samples_dd_with_custom_field_values:
        #                 custom_field_values = (
        #                     sample_data.ssn.sample_custom_field_value.all()
        #                 )
        #                 for custom_field_value in custom_field_values:
        #                     if custom_field_value.field.label == "Plot":
        #                         sample_data.plot = custom_field_value.value
        #                     if custom_field_value.field.label == "Cluster":
        #                         sample_data.cluster = custom_field_value.value

        #             return samples_dd_with_custom_field_values
        #         else:
        #             samples = (
        #                 SampleData.objects.filter(ssn__job_id=job_id)
        #                 .filter(Q(instrument__icontains="Alpha I"))
        #                 .select_related("ssn__sampleldsfdetail")
        #             )
        #             return samples

        #     else:
        #         return None
            
        
        if 'Alpha II' in instrument.name or 'Alpha_II' in instrument.name or 'Alpha II ' in instrument.name:
            if job_id is not None and instrument_id is not None:
                if job.sampling_design == 1:
                    samples_dd_with_custom_field_values = (
                        SampleData.objects.filter(ssn__job_id=job_id)
                        .filter(Q(instrument__icontains="Alpha II"))
                        .prefetch_related("ssn__sample_custom_field_value")
                    )

                    for sample_data in samples_dd_with_custom_field_values:
                        custom_field_values = (
                            sample_data.ssn.sample_custom_field_value.all()
                        )
                        for custom_field_value in custom_field_values:
                            if custom_field_value.field.label == "Plot":
                                sample_data.plot = custom_field_value.value
                            if custom_field_value.field.label == "Cluster":
                                sample_data.cluster = custom_field_value.value

                    return samples_dd_with_custom_field_values
                else:
                    samples = (
                        SampleData.objects.filter(ssn__job_id=job_id)
                        .filter(Q(instrument__icontains="Alpha II"))
                        .select_related("ssn__sampleldsfdetail")
                    )
                    return samples

            else:
                return None
            
        # if 'MPA' in instrument.name or 'mpa' in instrument.name:
        #     if job_id is not None and instrument_id is not None:
        #         if job.sampling_design == 1:
        #             samples_dd_with_custom_field_values = (
        #                 SampleData.objects.filter(ssn__job_id=job_id)
        #                 .filter(Q(instrument__icontains="MPA"))
        #                 .prefetch_related("ssn__sample_custom_field_value")
        #             )

        #             for sample_data in samples_dd_with_custom_field_values:
        #                 custom_field_values = (
        #                     sample_data.ssn.sample_custom_field_value.all()
        #                 )
        #                 for custom_field_value in custom_field_values:
        #                     if custom_field_value.field.label == "Plot":
        #                         sample_data.plot = custom_field_value.value
        #                     if custom_field_value.field.label == "Cluster":
        #                         sample_data.cluster = custom_field_value.value

        #             return samples_dd_with_custom_field_values
        #         else:
        #             samples = (
        #                 SampleData.objects.filter(ssn__job_id=job_id)
        #                 .filter(Q(instrument__icontains="MPA"))
        #                 .select_related("ssn__sampleldsfdetail")
        #             )
        #             return samples

        #     else:
        #         return None

        
        
        
        if instrument.name in ins_opus_files_version_one:
            if job_id is not None and instrument_id is not None:
                if job.sampling_design == 1:
                    samples_dd_with_custom_field_values = (
                        SampleData.objects.filter(ssn__job_id=job_id)
                        .filter(Q(instrument=instrument.name))
                        .prefetch_related("ssn__sample_custom_field_value")
                    )

                    for sample_data in samples_dd_with_custom_field_values:
                        custom_field_values = (
                            sample_data.ssn.sample_custom_field_value.all()
                        )
                        for custom_field_value in custom_field_values:
                            if custom_field_value.field.label == "Plot":
                                sample_data.plot = custom_field_value.value
                            if custom_field_value.field.label == "Cluster":
                                sample_data.cluster = custom_field_value.value

                    return samples_dd_with_custom_field_values
                else:
                    samples = (
                        SampleData.objects.filter(ssn__job_id=job_id)
                        .filter(Q(instrument=instrument.name))
                        .select_related("ssn__sampleldsfdetail")
                    )
                    return samples

            else:
                return None

        else:
            
            
            if job_id is not None and instrument_id is not None:
                if job.sampling_design == 1:
                    samples_dd_with_custom_field_values = (
                        SampleData.objects.filter(ssn__job_id=job_id)
                        .filter(Q(instrument__icontains=instrument.name))
                        .prefetch_related("ssn__sample_custom_field_value")
                    )

                    for sample_data in samples_dd_with_custom_field_values:
                        custom_field_values = (
                            sample_data.ssn.sample_custom_field_value.all()
                        )
                        for custom_field_value in custom_field_values:
                            if custom_field_value.field.label == "Plot":
                                sample_data.plot = custom_field_value.value
                            if custom_field_value.field.label == "Cluster":
                                sample_data.cluster = custom_field_value.value

                    return samples_dd_with_custom_field_values
                else:
                    samples = (
                        SampleData.objects.filter(ssn__job_id=job_id)
                        .filter(Q(instrument__icontains=instrument.name))
                        .select_related("ssn__sampleldsfdetail")
                    )
                            
                    
                    
                    return samples

            else:
                return None

    def get_context_data(self, *, object_list=None, **kwargs):

        context = super().get_context_data(**kwargs)
        context["show_download"] = (
            self.request.GET.get("job_id") is not None
            and self.request.GET.get("instrument_id") is not None
        )

        # Add job_number to context
        job_id = self.request.GET.get("job_id")
        if job_id:
            try:
                job = Job.objects.get(id=job_id)
                context["job_number"] = job.job_number
            except Job.DoesNotExist:
                context["job_number"] = None

        # Pagination
        paginator = Paginator(context["object_list"], self.paginate_by)
        page = self.request.GET.get("page")

        try:
            samples = paginator.page(page)
        except PageNotAnInteger:
            samples = paginator.page(1)
        except EmptyPage:
            samples = paginator.page(paginator.num_pages)

        context["samples"] = samples
        return context


from os import walk


class InstrumentJobDataFilesXrd(ListView):
    model = DataUpload
    template_name = "instruments/instrument_job_data_files_xrd.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.request.GET.get("job_id")
        instrument_id = self.request.GET.get("instrument_id")
        if job_id is None or instrument_id is None:
            raise Http404
        self.job = get_object_or_404(Job, pk=int(job_id))
        self.instrument = get_object_or_404(LabInstrument, pk=int(instrument_id))
        return super(InstrumentJobDataFilesXrd, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(InstrumentJobDataFilesXrd, self).get_context_data(**kwargs)
        context["instrument"] = self.instrument
        context["job"] = self.job
        return context

    def get_queryset(self):
        try:
            path_name = DataUpload.objects.filter(instrument__name="XRD").filter(
                job=self.job.id
            )
            # full_path = os.path.join(
            #     settings.MEDIA_ROOT, path_name[0].uploaded_file.name.split(".zip")[0]
            # )

            full_path = os.path.join(
                settings.MEDIA_ROOT, "jobs/data/XRD", str(path_name[0].job_id)
            )
            f = []
            for dirpath, dirnames, filenames in walk(full_path):
                for dir in dirnames:
                    binary_files = os.path.join(full_path, dir)
                    f.append({dir: os.listdir(binary_files)})

                for file in filenames:
                    if file.endswith(".xlsx"):
                        try:
                            excel_files = f[4]["excel files"]

                        except IndexError:
                            f.append({"excel files": filenames})

            data = {
                "job_id": self.job.id,
                "instrument": self.instrument.name,
                "raw_files": f,
                "job_number": self.job.job_number,
                "country": self.job.country,
                "region": self.job.region,
                "samples_received_on": self.job.samples_received_on,
            }

            return data
        except Exception as e:
            print(e)
            return "empty"


class InstrumentJobDataFilesTensor(ListView):
    model = DataUpload
    template_name = "instruments/instrument_job_data_files_tensor.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.request.GET.get("job_id")
        instrument_id = self.request.GET.get("instrument_id")
        if job_id is None or instrument_id is None:
            raise Http404
        self.job = get_object_or_404(Job, pk=int(job_id))
        self.instrument = get_object_or_404(LabInstrument, pk=int(instrument_id))
        return super(InstrumentJobDataFilesTensor, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(InstrumentJobDataFilesTensor, self).get_context_data(**kwargs)
        context["instrument"] = self.instrument
        context["job"] = self.job
        return context

    def get_queryset(self):
        try:
            path_name = DataUpload.objects.filter(
                instrument__name="Tensor 27 HTS-XT MIR"
            ).filter(job=self.job.id)
            full_path = os.path.join(
                settings.MEDIA_ROOT, path_name[0].uploaded_file.name.split(".zip")[0]
            )

            f = []
            for dirnames in walk(full_path):
                for dir in dirnames:
                    binary_files = os.path.join(full_path, dir)
                    f.append({dir: os.listdir(binary_files)})

            data = {
                "job_id": self.job.id,
                "instrument": self.instrument.name,
                "raw_files": f,
                "job_number": self.job.job_number,
                "country": self.job.country,
                "region": self.job.region,
                "samples_received_on": self.job.samples_received_on,
            }

            return data
        except Exception as e:
            print(e)
            return "empty"


class WetchemTemplateDownloadView(View):
    def get(self, request):
        template_name = "wetchem"
        # response content type
        response = HttpResponse(content_type="text/csv")
        # decide the file name
        response["Content-Disposition"] = f'attachment; filename="{template_name}.csv"'

        writer = csv.writer(response, csv.excel)
        response.write("\ufeff".encode("utf8"))

        # write the headers
        writer.writerow([*WETCHEM_CORE_FIELDS])

        return response


class QRBarCodeRegeneratorView(APIView):
    permission = AllowAny

    def get(self, request):
        directory = os.path.join(settings.MEDIA_ROOT, "jobs", "barcodes_backup")

        for subdir, dirs, files in os.walk(directory):
            for file in files:
                job_id = subdir.split("/")[-1]
                barcodes_rel_path = os.path.join("jobs", "barcodes", job_id)
                barcodes_abs_path = os.path.join(settings.MEDIA_ROOT, barcodes_rel_path)
                if not os.path.exists(barcodes_abs_path):
                    os.makedirs(barcodes_abs_path)
                sample = file.split(":")[0].split("_")[0]
                barcode_file_name = f"{sample[2:]}_bc"
                barcode_img = Code128(sample[2:], writer=ImageWriter())
                barcode_img.save(os.path.join(barcodes_abs_path, barcode_file_name))
                qr_file_name = f"{sample[2:]}_qr.png"
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=17,
                    border=10,
                )
                qr.add_data(sample[2:])
                qr.make(sample[2:])

                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_img.save(os.path.join(barcodes_abs_path, qr_file_name))

        return HttpResponse("codes generated")


def simple_upload(request):
    if request.method == "POST":
        myfile = request.FILES["myfile"]
        fs = FileSystemStorage()
        filename = fs.save(myfile.name, myfile)
        uploaded_file_url = fs.url(filename)

        return render(
            request, "intrument_jobs.html", {"uploaded_file_url": uploaded_file_url}
        )
    return render(request, "intrument_jobs.html")



def download_units_file(request, filename=""):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="data_units.csv"'
    writer = csv.writer(response)
    writer.writerow(["Variable", "Description", "Units"])
    try:
        # Create the HttpResponse object with the appropriate CSV header.
        unit_obj = WetChemSampleDataUnits.objects.get(id=1)
        data = WetChemSampleDataUnitsSerializer(unit_obj)

        for dat in data.data:
            writer.writerow(
                [
                    data.data[dat]["unit_one_variable"],
                    data.data[dat]["unit_one_description"],
                    data.data[dat]["unit_one_unit"],
                ]
            )

        return response

    except Exception as e:
        print(str(e))
        writer.writerow(["", "", ""])
        return response


job_number_start = 301
chem_suit_key = 246
v1_samples_col_list = [
    "SSN",
    "ossn",
    "job_no",
    "study",
    "scientist",
    "site",
    "region",
    "country",
    "material",
    "sdesign",
    "cluster",
    "plot",
    "dstd",
    "dtop",
    "dsub",
    "treat",
    "lab",
    "Compart",
    "Bay",
    "Tray",
    "Pos",
    "Wt",
]

v1_jobs_col_list = [
    "Job No",
    "Analyses",
    "Quantity",
    "Materail",
    "Sampling",
    "Site",
    "Study",
    "Scientist",
    "Country",
    "Additional info",
]


def jobs_migrations(request):
    for i in range(0, 1 + 1):
        job_no = job_number_start + i
        job_number_v1 = "ICR{}2017".format(str(job_no))

        try:
            jobs_csv_path = os.path.join(
                settings.MEDIA_ROOT, "migration_data/jobs2.xlsx"
            )

            samples_csv_path = os.path.join(
                settings.MEDIA_ROOT, "migration_data/sample_details.csv"
            )

            samples_df = pd.read_csv(
                samples_csv_path, usecols=v1_samples_col_list, low_memory=False
            )
            sample_values = samples_df["job_no"] == job_number_v1
            samples_data = samples_df[sample_values].head(1)

            jobs_df = pd.read_excel(jobs_csv_path, usecols=v1_jobs_col_list)

            sample_values = jobs_df["Job No"] == job_number_v1

            jobs_data = jobs_df[sample_values].head(1)
            # create the correct format for the job number
            str1 = job_number_v1[:3]
            str2 = job_number_v1[3:6].lstrip("0")
            str3 = job_number_v1[6:]

            v1_samples_key = samples_data.iloc[0].name
            v1_jobs_key = jobs_data.iloc[0].name

            # assign default user from the database
            user = CustomUser.objects.get(email="admin@gmail.com")
            # create a job from the form data
            job = Job.objects.get_or_create(
                job_number="{}-{}-{}".format(str1, str2, str3),
                disposition=2,
                sampling_design=(
                    0 if samples_data["sdesign"][v1_samples_key] == "ldsf" else 1
                ),
                country=pycountry.countries.search_fuzzy("Kenya")[0].alpha_2,
                region=samples_data["region"][v1_samples_key],
                project=samples_data["study"][v1_samples_key],
                site=samples_data["site"][v1_samples_key],
                created_by=user,
                scientist_name=samples_data["scientist"][v1_samples_key],
                scientist_email="",
                testing_authorized_by=user,
                plant=(
                    {"plant": str(jobs_data["Quantity"][v1_jobs_key])}
                    if jobs_data["Materail"][v1_jobs_key] == "plant"
                    else ""
                ),
                soil=(
                    {"soil": str(jobs_data["Quantity"][v1_jobs_key])}
                    if jobs_data["Materail"][v1_jobs_key] == "soil"
                    else ""
                ),
                fertilizer=(
                    {"fertilizer": str(jobs_data["Quantity"][v1_jobs_key])}
                    if jobs_data["Additional info"][v1_jobs_key] == "Fertilizer"
                    else ""
                ),
                other=(
                    {
                        jobs_data["Additional info"][v1_jobs_key]: str(
                            jobs_data["Quantity"][v1_jobs_key]
                        )
                    }
                    if jobs_data["Materail"][v1_jobs_key] == "others"
                    else ""
                ),
            )

            schedules_migrations(job_number_v1, v1_jobs_key)
            serializer = JobSerializer(job)
            # jobs_samples_migrations(job_number_v1, v1_jobs_key)

            return HttpResponse(serializer.data)
        except Exception as e:
            # print(e, "------------")
            continue


def jobs_samples_migrations(job_number_v1, v1_jobs_key):
    """script to migrate sample details into the database"""
    # try:

    # create the correct format for the job number
    str1 = job_number_v1[:3]
    str2 = job_number_v1[3:6].lstrip("0")
    str3 = job_number_v1[6:]

    # create a job from the form data
    job = Job.objects.get_or_create(
        job_number="{}-{}-{}".format(str1, str2, str3),
    )
    serializer = JobSerializer(job)

    # add samples for the specific job id to the
    # database
    samples = []
    samples_details = []

    samples_csv_path = os.path.join(
        settings.MEDIA_ROOT, "migration_data/sample_details.csv"
    )
    samples_df = pd.read_csv(
        samples_csv_path, usecols=v1_samples_col_list, low_memory=False
    )

    job_values = samples_df["job_no"] == job_number_v1

    try:
        for index, row in samples_df[job_values].iterrows():
            row_dict = {
                "cluster": row["cluster"],
                "plot": row["plot"],
                "depth_std": row["dstd"],
                "depth_top": row["dtop"],
                # "depth_bottom": "",
                # "air_dried_wt": "",
                # "coarse_wt": "",
            }  # to be updated

            # add ldsf samples
            if row["sdesign"] == "ldsf":
                try:
                    sample_det = Sample.objects.get(number=str(row["ossn"]))
                    SampleLDSFDetail.objects.filter(sample=sample_det).update(
                        **row_dict
                    )
                except Sample.DoesNotExist:
                    job_id = job[0].id

                    sample = Sample.objects.get_or_create(
                        number=str(row["ossn"]), job_id=job_id, version_one=True
                    )
                    samples.append(sample[0])
                    # continue
                    sample_instance = Sample.objects.get(number=sample[0].number)
                    details = SampleLDSFDetail(**row_dict, sample=sample_instance)
                    samples_details.append(details)

            # add non ldsf samples
            elif row["sdesign"] == "nldsf":  # Non LDSF samples
                values = []
                field_names = []
                fields = [
                    "ossn",
                    "study",
                    "region",
                    "country",
                    "material",
                    "sdesign",
                    "cluster", 
                    "plot",
                    # "dstd",
                    # "dtop",
                    # "dsub",
                    "treat",
                    "lab",
                    "Compart",
                    "Bay",
                    "Tray",
                    "Pos",
                    "Wt",
                ]

                job_id = job[0].id
                sample = Sample.objects.get_or_create(
                    number=str(row["ossn"]), job_id=job_id, version_one=True
                )
                samples.append(sample[0])

                # custom fields for non ldsf samples
                for field_name in fields:
                    field, created = CustomField.objects.get_or_create(label=field_name)
                    field.jobs.add(job_id)

                    sample_instance = Sample.objects.get(number=sample[0].number)
                    values.append(
                        CustomFieldValue(
                            field=field, sample=sample_instance, value=row[field_name]
                        )
                    )

                try:
                    CustomFieldValue.objects.bulk_create(values)
                except:
                    continue

        if samples:
            job[0].samples_uploaded_at = timezone.now()
            job[0].save()
            create_barcodes(job_id=job_id, samples=samples)

        SampleLDSFDetail.objects.bulk_create(samples_details)

        # schedules_migrations(job_number_v1, v1_jobs_key)
        return HttpResponse("samples uploaded")
    except Exception as e:
        return HttpResponse(str(e))


def schedules_migrations(job_number_v1, v1_schedules_key):
    schedules_key = v1_schedules_key + 10

    try:
        col_list = [
            "service_no",
            "indiv_ana",
            "date_recieved",
            "date_logged",
            "author_by",
            "chem_suite",
        ]
        csv_path = os.path.join(settings.MEDIA_ROOT, "migration_data/schedules-1.csv")
        # read the csv file
        dff = pd.read_csv(
            csv_path,
            usecols=col_list,
        )

        job_numbers = dff["service_no"] == job_number_v1
        job_data = dff[job_numbers].head(1)

        tests_done = job_data["indiv_ana"][schedules_key].split(".")
        # wetchem = job_data["chem_suite"][chem_suit_key]

        # wetchem_test = job_data["chem_suite"]

        # format the service number/job number
        str1 = job_number_v1[:3]
        str2 = job_number_v1[3:6].lstrip("0")
        str3 = job_number_v1[6:]

        # replace prf, mirh, mira, nir with version 2 instrument names
        updated_tests_done = [
            s.replace("mirh", "Tensor 27 HTS-XT MIR")
            .replace("nir", "MPA_FTNIR_1")
            .replace("mira", "KBr")
            .replace("pxrf", "pXRF")
            .replace("mpa", "MPA_FTNIR_1")
            .replace("KBr", "Alpha KBr")
            .replace("ZnSe", "Alpha ZnSe_1")
            .replace("txrf", "TXRF")
            .replace("ph", "pH")
            for s in tests_done
        ]

        # loop through the list of tests from the test column and
        # assign the tests to the respective job
        for test in updated_tests_done:
            # format job number
            job_no = "{}-{}-{}".format(str1, str2, str3)

            # get the job number
            job = Job.objects.filter(job_number=job_no)

            # get the respective test
            test_id = LabTest.objects.filter(instrument__name__icontains=test)

            # assign the test to the job
            job[0].tests.add(test_id[0].id)
            job_tests = JobTest.objects.filter(job=job[0].id)

            # update start date, end date, completion status and assignee id
            for job_test in job_tests:
                received_split_date = (
                    job_data["date_recieved"][schedules_key].split()[0].split("/")[::-1]
                )
                receoved_formated_date = "{}-{}-{}".format(
                    received_split_date[0],
                    received_split_date[2],
                    received_split_date[1],
                )
                job_test.start_date = receoved_formated_date

                logged_split_date = job_data["date_logged"][schedules_key].split("/")[
                    ::-1
                ]
                logged_formated_date = "{}-{}-{}".format(
                    logged_split_date[0], logged_split_date[2], logged_split_date[1]
                )
                job_test.end_date = logged_formated_date

                job.update(completion_status=2)
                job.update(samples_received_on=receoved_formated_date)

                created_at_date = "{}-{}-{}".format(
                    logged_split_date[2], logged_split_date[1], logged_split_date[0]
                )
                created_at = datetime.strptime(created_at_date, "%m-%d-%Y").date()

                job.update(created_at=created_at)
                job.update(testing_authorized_at=created_at)

                job_test.completion_status = 2

                job_test.save()

        return HttpResponse("hey")

    except Exception as e:
        pass


def migrate_users(self):
    col_list = ["username", "email"]
    csv_path = os.path.join(settings.MEDIA_ROOT, "migration_data/users.csv")
    # read the csv file containing users data
    df = pd.read_csv(
        csv_path,
        usecols=col_list,
    )

    usernames = df["username"]
    emails = df["email"]

    length_usernames = len(usernames)

    user_details = []
    for i in range(0, length_usernames):
        details = {"username": usernames[i], "email": emails[i]}
        user_details.append(details)

    for details in user_details:
        User.objects.create(
            is_superuser=False, email=details["email"], name=details["username"]
        )
    return HttpResponse("hey")


class MissingDataView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # samples = Sample.objects.filter(Q(job_id__job_number__icontains='2016'))
        # samples =  Sample.objects.filter(number='125361')

        # add missing study values in samples
        # samples_csv_path = os.path.join(
        # settings.MEDIA_ROOT, "migration_data/sample_details.csv"
        # )

        schedules_csv_path = os.path.join(
            settings.MEDIA_ROOT, "migration_data/schedules-1.csv"
        )

        # samples_df = pd.read_csv(
        #     samples_csv_path, usecols=v1_samples_col_list, low_memory=False
        # )

        schedules_df = pd.read_csv(schedules_csv_path, low_memory=False)

        jobs = Job.objects.filter(
            Q(job_number__icontains="2014") | Q(job_number__icontains="2015")
        ).filter(id__range=(178, 197))

        for job in jobs:
            try:
                FF = job.job_number

                shcedules_vf = schedules_df["service_no"] == "".join(
                    (FF[:4], "00", FF[4:])
                ).replace("-", "")

                schedule_excel = schedules_df[shcedules_vf].head(1)

                dispose_status = schedule_excel["dispose"].item()

                if dispose_status == "Archive":
                    job.disposition = 2
                elif dispose_status == "Dispose":
                    job.disposition == 1
                else:
                    job.disposition == 0

                job.save()

            except Exception as e:
                continue

        return HttpResponse("done")


# class SearchSsnView(APIView):
#     """
#     View searching for SSN via samples uploaded
#     """

#     permission_classes = [AllowAny]

#     def post(self, request):
#         try:
#             sample = Sample.objects.get(number=request.data.upper())
#             job = Job.objects.get(id=sample.job.id)
#             return Response({"job_number": job.job_number, "status": True})
#         except Exception as e:
#             return Response({"status": False})


# class SearchJobView(APIView):
#     """
#     View for searching a Job by any relevant field in the Job or Sample models.
#     """

#     permission_classes = [AllowAny]

#     def post(self, request):
#         try:
#             search_query = request.data.get("query").upper()

#             # Search in Job model fields
#             job = Job.objects.filter(
#                 Q(job_number__icontains=search_query) |
#                 Q(country__icontains=search_query) |
#                 Q(region__icontains=search_query) |
#                 Q(project__icontains=search_query) |
#                 Q(site__icontains=search_query) |
#                 Q(scientist_name__icontains=search_query) |
#                 Q(scientist_email__icontains=search_query)
#             ).first()

#             if job:
#                 return Response({"job_number": job.job_number, "status": True})

#             # Search in Sample model fields
#             sample = Sample.objects.filter(
#                 Q(number__icontains=search_query)
#             ).first()

#             if sample:
#                 job = sample.job
#                 return Response({"job_number": job.job_number, "status": True})

#             return Response({"status": False})


#         except Exception as e:
#             return Response({"status": False, "error": str(e)})
class SearchJobView(APIView):
    def get(self, request):
        query = request.query_params.get("q", None)
        if query:
            jobs = Job.objects.filter(
                Q(job_number__icontains=query)
                | Q(country__icontains=query)
                | Q(region__icontains=query)
                | Q(project__icontains=query)
                | Q(site__icontains=query)
                | Q(samples__number__icontains=query)
            ).distinct()

            serializer = JobSerializer(jobs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(
            {"error": "No search query provided"}, status=status.HTTP_400_BAD_REQUEST
        )




class RetreiveProjectDocumentation(viewsets.ModelViewSet):
    def get_serializer_context(self):
        context = super(RetreiveProjectDocumentation, self).get_serializer_context()
        context["instrument"] = self.request.query_params.get("instrument_id")
        return context

    def get_queryset(self):
        if self.request.user.has_perm("jobs.can_view_jobs"):
            jobs = Job.objects.all()
        else:
            jobs = Job.objects.filter(created_by=self.request.user)

        search = self.request.query_params.get("search")

        if search is not None:
            return jobs.filter(job_number__icontains=search)

        return jobs.select_related("created_by")

    def get_serializer_class(self):
        if self.action == "get":
            return JobListSerializer

    def get(self, request, id):
        pass



from .serializers import (
    JobListSerializer,
    ProjectDocumentationUploadSerializer,
    JobsProjectDocumentationUploadSerializer,
)


class ProjectDocumentationViewSet(viewsets.ModelViewSet):
    parser_classes = [MultiPartParser, FileUploadParser]
    PAGINATION_SIZE = 10
    serializer_class = ProjectDocumentationUploadSerializer

    def get_user_upload_reports_perms(self, user):
        # Get all permissions assigned to the user
        # user_perms = self.request.user.get_all_permissions()

        # # Filter permissions that start with "Upload Reports"
        # upload_reports_perms = [perm for perm in user_perms if perm.split('.')[-1].startswith("upload_reports")]
        user_perms = Permission.objects.filter(user=user) | Permission.objects.filter(
            group__user=user
        )

        # Filter permissions that start with "upload_reports" and get their names
        upload_reports_perms = [
            perm.name  # Get the name field of the Permission
            for perm in user_perms.distinct()  # Use distinct to avoid duplicates
            if perm.codename.startswith("upload_reports")
        ]
        
        
        return upload_reports_perms

    @action(detail=False, methods=["get"])
    def reports(self, request):
        
        

        user = self.request.user
        user_organization = user.organization
        organization_id = self.request.query_params.get("organization")

        # Apply search filter
        search = self.request.query_params.get("search")
        # Start with all ProjectDocumentationUpload
        base_queryset = ProjectDocumentationUpload.objects.all()

        # Filter by organization if not Regional Admin
        if (
            self.request.user.groups.filter(name="Regional Admin").exists()
            or self.request.user.is_superuser
        ):

            base_queryset = base_queryset.filter(job__organization=user_organization)
        # elif self.request.user.groups.filter(name="Regional Admin").exists():

        #     base_queryset = base_queryset.filter()

        else:
            user_permissions = self.get_user_upload_reports_perms(request.user)
            permission_filters = Q()

            for permissions in user_permissions:

                # country_name= [item.replace(' ', '') for item in permissions.split('-')][2]
                country_name = permissions.split("-")[2].strip()
                # formatted_country_name = country_name.replace('-', ' ')

                organization_name = permissions.split("-")[1].strip()
                # organization_name = [item.replace(' ', '') for item in permissions.split('-')][1]
                country = pycountry.countries.search_fuzzy(country_name)[0]
                country_codee = country.alpha_2
                
                permission_filters |= Q(
                    job__organization__name=organization_name,
                    job__organization__country=country_codee,
                )
                
                


            if permission_filters:
                base_queryset = base_queryset.filter(permission_filters)
            else:

                base_queryset = base_queryset.filter(
                    job__organization=user_organization
                )

        # If organization_id is provided in URL, filter by it (overrides user_organization for Regional Admin)
        if organization_id:
            base_queryset = base_queryset.filter(job__organization_id=organization_id)

        # Apply search filter if provided
        if search:
            try:
                country = pycountry.countries.search_fuzzy(search)[0]
                country_code = country.alpha_2
            except LookupError:
                country_code = None

            search_query = (
                Q(job__job_number__icontains=search)
                | Q(job__scientist_name__icontains=search)
                | Q(job__country__icontains=search)
                | Q(job__region__icontains=search)
                | Q(job__project__icontains=search)
                | Q(job__site__icontains=search)
                | Q(job__samples__number__icontains=search)
                | Q(project_title__icontains=search)
            )

            if country_code:
                search_query |= Q(job__country=country_code)

            base_queryset = base_queryset.filter(search_query)

        # Final ordering
        # jobs = base_queryset.order_by('-job__id').distinct('job__id')
        # Final ordering and grouping
        jobs = (
            base_queryset.values("job__id")
            .annotate(
                doc_count=Count("id"),
                completed_count=Count("id", filter=Q(completion_status=2)),
                all_completed=Case(
                    When(
                        doc_count=Count("id", filter=Q(completion_status=2)), then=True
                    ),
                    default=False,
                    output_field=BooleanField(),
                ),
            )
            .order_by("-job__created_at")
        )
        # Pagination
        page = request.query_params.get("page", 1)
        paginator = Paginator(jobs, self.PAGINATION_SIZE)
        page_obj = paginator.get_page(page)

        tasks_dict = {}

        # for task in page_obj:
        for job_data in page_obj:
            job_id = job_data["job__id"]
            job = Job.objects.get(id=job_id)
            job_number = job.job_number

            tasks_dict[job_number] = {
                "job": {
                    "id": job_id,
                    "job_number": job_number,
                    "scientist_name": job.scientist_name,
                    "country": job.country,
                    "region": job.region,
                    "project": job.project,
                    "site": job.site,
                    "created_at": job.created_at,
                    "completion_status": (
                        "Completed" if job_data["all_completed"] else "Not Completed"
                    ),
                },
                "reports": [],
            }
            # job_tests_data = ProjectDocumentationUploadSerializer(task).data

            # job_number = job_tests_data["job"]["job_number"]

            # job_id =  task.job.id
            # if job_number not in tasks_dict:
            #     tasks_dict[job_number] = []
            # tasks_dict[job_number].append(job_tests_data)

        if self.request.user.groups.filter(name="Regional Admin").exists():
            users_obj = User.objects.filter()
        else:
            country = pycountry.countries.get(
                alpha_2=self.request.user.organization.country
            )
            country_name = country.name
            group_name = f"Upload Reports - {user_organization.name} - {country_name}"
            users_obj = User.objects.filter(groups__name=group_name).distinct()
            # users_obj =  User.objects.filter(orga)

        users_serializer = UserSerializer(users_obj, many=True)
        response_data = {
            "users": users_serializer.data,
            "results": tasks_dict,
            "pagination": {
                "current_page": page_obj.number,
                "num_pages": page_obj.paginator.num_pages,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            },
        }

        if self.request.user.groups.filter(name="Regional Admin").exists():
            organizations = Organization.objects.all()
            response_data["organizations"] = [
                {
                    "id": org.id,
                    "name": org.name,
                    "country": pycountry.countries.get(alpha_2=org.country).name,
                }
                for org in organizations
            ]

        
        
        return Response(response_data, template_name="project_documentation.html")

    def retrieve(self, request, *args, **kwargs):

        job = super(ProjectDocumentationViewSet, self).retrieve(
            request, *args, **kwargs
        )
        if request.accepted_renderer.format == "html":
            job.template_name = "job.html"
            job.data = {"job": job.data}
        return job

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FileUploadParser],
    )
    def upload(self, request):
        try:
            project_documentation_files_dir = os.path.join(
                settings.MEDIA_ROOT,
                "project_documentation",
            )
            form_data = json.loads(request.data["formData"])
            job = Job.objects.get(job_number=form_data["jobNumber"])

            category = Category.objects.get(id=int(form_data["selectedId"]))

            data = {
                "project_title": form_data["projectTitle"],
                "project_description": form_data["projectDescription"],
                "sent_to_client": datetime.strptime(form_data["sentDate"], "%Y-%m-%d"),
                "job": job,
                "uploaded_by": self.request.user,
                "category": category,
            }
            files = request.FILES.getlist("files")

            location = project_documentation_files_dir
            fs = OverwriteStorageProjectDocumentation(location=location)

            project_obj = ProjectDocumentationUpload.objects.get_or_create(**data)

            for file in files:
                fs.save(
                    os.path.join(
                        "{}".format(str(job.id)),
                        "{}".format(str(project_obj[0].id)),
                        file.name,
                    ),
                    file,
                )

            file_path = os.path.join(
                settings.MEDIA_ROOT,
                project_documentation_files_dir,
                str(job.id),
                str(project_obj[0].id),
            )

            shutil.make_archive(
                "{}".format(file_path, str(project_obj[0].id)), "zip", file_path
            )

            return Response(status=status.HTTP_201_CREATED)
        except Exception as e:
            raise e

    def update(self, request):

        try:
            report_id = request.GET.get("report", None)
            project_documentation_files_dir = os.path.join(
                settings.MEDIA_ROOT,
                "project_documentation",
            )

            form_data = request.data
            job = Job.objects.get(id=form_data["jobNumber"])
            # category = Category.objects.get(id=int(form_data["selectedId"]))
            sent_date_str = form_data.get("sentDate")
            
            
            
            
            # date_part = sent_date_str.split("T")[0]
            # sent_date = datetime.strptime(date_part, "%Y-%m-%d").date()
            date = datetime.datetime.strptime(sent_date_str[:24], "%a %b %d %Y %H:%M:%S")
            sent_date = date.strftime("%Y-%m-%d")

            data = {
                "project_title": form_data["projectTitle"],
                "project_description": form_data["projectDescription"],
                "sent_to_client": sent_date,
                "job": job,
                "uploaded_by": self.request.user,
            }
            # category

            files = request.FILES.getlist("files")
            location = project_documentation_files_dir
            fs = OverwriteStorageProjectDocumentation(location=location)

            project_documentation = get_object_or_404(
                ProjectDocumentationUpload, id=report_id
            )

            # Update the object with new data
            project_documentation.project_title = form_data["projectTitle"]
            project_documentation.project_description = form_data["projectDescription"]
            # sent_to_client_date = datetime.strptime(form_data["sentDate"], "%Y-%m-%d").date()
            sent_to_client_date = sent_date
            if sent_to_client_date:
                project_documentation.sent_to_client = sent_to_client_date
            project_documentation.job = job
            project_documentation.uploaded_by = self.request.user

            # Save the updated object
            project_documentation.save()

            # Temporary directory path based on job.id and report_id
            temp_dir_path = os.path.join(
                settings.MEDIA_ROOT, "temp", str(job.id), str(report_id)
            )

            # Ensure the temporary directory exists
            os.makedirs(temp_dir_path, exist_ok=True)

            # Save files to the temporary directory
            for file in files:
                temp_file_path = os.path.join(temp_dir_path, file.name)
                with open(temp_file_path, "wb+") as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)

            # Path where the zip archive will be saved (without '.zip' extension, as shutil.make_archive adds it)
            archive_path = os.path.join(
                settings.MEDIA_ROOT,
                "project_documentation",
                str(job.id),
                str(report_id),
            )

            # Create a zip archive of the temporary directory
            shutil.make_archive(archive_path, "zip", temp_dir_path)

            # Delete the temporary directory and its contents
            shutil.rmtree(temp_dir_path)

            return Response(status=status.HTTP_201_CREATED)
        except Exception as e:
            raise e


# class ProjectDocumentationViewSet(viewsets.ModelViewSet):
#     """
#     View project documentation for all jobs
#     """

#     parser_classes = [MultiPartParser, FileUploadParser]

#     # permission_classes = [ProjectDocumentationPermission]

#     def get_queryset(self):
#         # if self.request.user.has_perm("jobs.can_view_jobs"):
#         if self.request.user.organization.name == 'ICRAF' and self.request.user.organization.country == 'KE':

#             jobs_obj = Job.objects.all()

#             jobs =  sorted(jobs_obj, key=lambda job: parse_job_number(job.job_number), reverse=True)

#         else:
#             # jobs_obj = Job.objects.filter(created_by=self.request.user)
#             jobs = Job.objects.filter(organization=self.request.user.organization)

#         search = self.request.query_params.get("search")

#         if search is not None:
#             return jobs.filter(job_number__icontains=search)

#         return jobs

#     def get_serializer_class(self):
#         if self.action == "list":
#             return JobListSerializer
#         if self.action in ("create", "upload", "PUT"):
#             return ProjectDocumentationUploadSerializer

#     def list(self, request, *args, **kwargs):
#         jobs = super(ProjectDocumentationViewSet, self).list(request, *args, **kwargs)
#         if request.accepted_renderer.format == "html":
#             jobs.template_name = "project_documentation.html"
#             jobs.data = {"jobs": jobs.data}
#             if "instrument_id" in request.query_params:
#                 jobs.data.update({"instrument": True})
#             if "success" in request.query_params:
#                 messages.success(request, message=request.query_params["success"])

#         paginator = Paginator(jobs.data["jobs"], 8)
#         page_number = request.GET.get("page")
#         if page_number == None:
#             page_number = 1
#         page_obj = paginator.get_page(page_number)
#         page_obj.adjusted_elided_pages = paginator.get_elided_page_range(
#             int(page_number)
#         )

#         new_list = []

#         for x in page_obj:
#             projects = ProjectDocumentationUpload.objects.filter(job=x["id"])[:10]

#             serializer = JobsProjectDocumentationUploadSerializer(projects, many=True)

#             reports = []  # Initialize the reports list for each job outside the loop

#             if len(serializer.data) > 0:
#                 for report_data in serializer.data:
#                     print(report_data["id"])

#                     reports.append(
#                         {
#                             "id": report_data["id"],
#                             "name": report_data["report"]["name"],
#                             "is_uploaded": report_data["is_uploaded"],
#                             "job_id": report_data["job"]["id"],
#                         }
#                     )

#             new_list.append(
#                 {
#                     "id": x["id"],
#                     "scientist_name": x["scientist_name"],
#                     "sampling_design": x["sampling_design"],
#                     "country": x["country"],
#                     "region": x["region"],
#                     "project": x["project"],
#                     "site": x["site"],
#                     "job_number": x["job_number"],
#                     "reports": reports,  # Append all reports for this job
#                 }
#             )

#         return render(
#             request,
#             "project_documentation.html",
#             {"page_obj": page_obj, "data": new_list},
#         )

#         # return jobs

#     def retrieve(self, request, *args, **kwargs):
#         job = super(ProjectDocumentationViewSet, self).retrieve(
#             request, *args, **kwargs
#         )
#         if request.accepted_renderer.format == "html":
#             job.template_name = "job.html"
#             job.data = {"job": job.data}
#         return job

#     @action(
#         detail=True,
#         methods=["post"],
#         parser_classes=[MultiPartParser, FileUploadParser],
#     )
#     def upload(self, request):
#         try:
#             project_documentation_files_dir = os.path.join(
#                 settings.MEDIA_ROOT,
#                 "project_documentation",
#             )
#             form_data = json.loads(request.data["formData"])
#             job = Job.objects.get(job_number=form_data["jobNumber"])
#             print(
#                 form_data,
#                 "select id >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",
#             )

#             print(
#                 form_data["selectedId"],
#                 "select id >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",
#             )
#             category = Category.objects.get(id=int(form_data["selectedId"]))

#             data = {
#                 "project_title": form_data["projectTitle"],
#                 "project_description": form_data["projectDescription"],
#                 "sent_to_client": datetime.strptime(form_data["sentDate"], "%Y-%m-%d"),
#                 "job": job,
#                 "uploaded_by": self.request.user,
#                 "category": category,
#             }
#             files = request.FILES.getlist("files")

#             location = project_documentation_files_dir
#             fs = OverwriteStorageProjectDocumentation(location=location)

#             project_obj = ProjectDocumentationUpload.objects.get_or_create(**data)

#             for file in files:
#                 fs.save(
#                     os.path.join(
#                         "{}".format(str(job.id)),
#                         "{}".format(str(project_obj[0].id)),
#                         file.name,
#                     ),
#                     file,
#                 )

#             file_path = os.path.join(
#                 settings.MEDIA_ROOT,
#                 project_documentation_files_dir,
#                 str(job.id),
#                 str(project_obj[0].id),
#             )

#             shutil.make_archive(
#                 "{}".format(file_path, str(project_obj[0].id)), "zip", file_path
#             )

#             return Response(status=status.HTTP_201_CREATED)
#         except Exception as e:
#             raise e

#     def update(self, request):

#         try:
#             report_id = request.GET.get('report', None)
#             project_documentation_files_dir = os.path.join(
#                 settings.MEDIA_ROOT,
#                 "project_documentation",
#             )

#             form_data = json.loads(request.data["formData"])
#             job = Job.objects.get(id=form_data["jobNumber"])
#             # category = Category.objects.get(id=int(form_data["selectedId"]))

#             data = {
#                 "project_title": form_data["projectTitle"],
#                 "project_description": form_data["projectDescription"],
#                 "sent_to_client": datetime.strptime(form_data["sentDate"], "%Y-%m-%d"),
#                 "job": job,
#                 "uploaded_by": self.request.user,
#             }
#             # category

#             files = request.FILES.getlist("files")
#             location = project_documentation_files_dir
#             fs = OverwriteStorageProjectDocumentation(location=location)


#             project_documentation = get_object_or_404(ProjectDocumentationUpload, id=report_id)

#             # Update the object with new data
#             project_documentation.project_title = form_data["projectTitle"]
#             project_documentation.project_description = form_data["projectDescription"]
#             sent_to_client_date = datetime.strptime(form_data["sentDate"], "%Y-%m-%d").date()
#             if sent_to_client_date:
#                 project_documentation.sent_to_client = sent_to_client_date
#             project_documentation.job =job
#             project_documentation.uploaded_by = self.request.user

#             # Save the updated object
#             project_documentation.save()

#             # Temporary directory path based on job.id and report_id
#             temp_dir_path = os.path.join(settings.MEDIA_ROOT, "temp", str(job.id), str(report_id))

#             # Ensure the temporary directory exists
#             os.makedirs(temp_dir_path, exist_ok=True)

#             # Save files to the temporary directory
#             for file in files:
#                 temp_file_path = os.path.join(temp_dir_path, file.name)
#                 with open(temp_file_path, 'wb+') as destination:
#                     for chunk in file.chunks():
#                         destination.write(chunk)

#             # Path where the zip archive will be saved (without '.zip' extension, as shutil.make_archive adds it)
#             archive_path = os.path.join(settings.MEDIA_ROOT, "project_documentation", str(job.id), str(report_id))

#             # Create a zip archive of the temporary directory
#             shutil.make_archive(archive_path, 'zip', temp_dir_path)

#             # Delete the temporary directory and its contents
#             shutil.rmtree(temp_dir_path)

#             return Response(status=status.HTTP_201_CREATED)
#         except Exception as e:
#             raise e


class PpViewSet(viewsets.ModelViewSet):
    """
    View project documentation for all jobs
    """

    # parser_classes = [MultiPartParser, FileUploadParser]

    # permission_classes = [ProjectDocumentationPermission]

    def get_queryset(self):
        if self.request.user.has_perm("jobs.can_view_jobs"):
            jobs = Job.objects.all()
        else:
            jobs = Job.objects.filter(created_by=self.request.user)

        search = self.request.query_params.get("search")

        if search is not None:
            return jobs.filter(job_number__icontains=search)

        return jobs.select_related("created_by")

    def get_serializer_class(self):
        if self.action == "list":
            return JobListSerializer
        if self.action in ("create", "upload"):
            return ProjectDocumentationUploadSerializer
        if self.action == "schedule":
            return ReportScheduleSerializer

    def list(self, request, *args, **kwargs):
        jobs = super(PpViewSet, self).list(request, *args, **kwargs)
        if request.accepted_renderer.format == "html":
            jobs.template_name = "project_documentation_consolidated_data.html"
            jobs.data = {"jobs": jobs.data}
            if "instrument_id" in request.query_params:
                jobs.data.update({"instrument": True})
            if "success" in request.query_params:
                messages.success(request, message=request.query_params["success"])

        paginator = Paginator(jobs.data["jobs"], 7)
        page_number = request.GET.get("page")
        if page_number == None:
            page_number = 1
        page_obj = paginator.get_page(page_number)
        page_obj.adjusted_elided_pages = paginator.get_elided_page_range(
            int(page_number)
        )

        new_list = []

        new_list = []

        for x in page_obj:
            job_report = ProjectDocumentationUpload.objects.filter(job_id=x["id"])
            serializer = JobsProjectDocumentationUploadSerializer(job_report, many=True)

            reports = []  # Initialize the reports list for each job outside the loop

            if len(serializer.data) > 0:
                for report_data in serializer.data:
                    reports.append(
                        {
                            "id": report_data["id"],
                            "name": report_data["report"]["name"],
                            "is_uploaded": report_data["is_uploaded"],
                        }
                    )

            new_list.append(
                {
                    "id": x["id"],
                    "scientist_name": x["scientist_name"],
                    "sampling_design": x["sampling_design"],
                    "country": x["country"],
                    "region": x["region"],
                    "project": x["project"],
                    "site": x["site"],
                    "job_number": x["job_number"],
                    "reports": reports,  # Append all reports for this job
                }
            )
        return render(
            request,
            "project_documentation_consolidated_data.html",
            {"page_obj": page_obj, "data": new_list},
        )

        # return jobs

    def retrieve(self, request, *args, **kwargs):
        job = super(ProjectDocumentationViewSet, self).retrieve(
            request, *args, **kwargs
        )
        if request.accepted_renderer.format == "html":
            job.template_name = "job.html"
            job.data = {"job": job.data}
        return job

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FileUploadParser],
    )
    def upload(self, request):
        try:
            project_documentation_files_dir = os.path.join(
                settings.MEDIA_ROOT,
                "project_documentation",
            )
            form_data = json.loads(request.data["formData"])
            job = Job.objects.get(job_number=form_data["jobNumber"])

            category = Category.objects.get(id=int(form_data["selectedId"]))

            data = {
                "project_title": form_data["projectTitle"],
                "project_description": form_data["projectDescription"],
                "sent_to_client": datetime.strptime(form_data["sentDate"], "%Y-%m-%d"),
                "job": job,
                "uploaded_by": self.request.user,
                "category": category,
            }
            files = request.FILES.getlist("files")

            location = project_documentation_files_dir
            fs = OverwriteStorageProjectDocumentation(location=location)

            project_obj = ProjectDocumentationUpload.objects.get_or_create(**data)

            for file in files:
                fs.save(
                    os.path.join(
                        "{}".format(str(job.id)),
                        "{}".format(str(project_obj[0].id)),
                        file.name,
                    ),
                    file,
                )

            file_path = os.path.join(
                settings.MEDIA_ROOT,
                project_documentation_files_dir,
                str(job.id),
                str(project_obj[0].id),
            )

            shutil.make_archive(
                "{}".format(file_path, str(project_obj[0].id)), "zip", file_path
            )

            return Response(status=status.HTTP_201_CREATED)
        except Exception as e:
            raise e

    def update(self, request):
        try:
            project_documentation_files_dir = os.path.join(
                settings.MEDIA_ROOT,
                "project_documentation",
            )

            form_data = json.loads(request.data["formData"])
            job = Job.objects.get(job_number=form_data["jobNumber"])
            category = Category.objects.get(id=int(form_data["selectedId"]))

            data = {
                "project_title": form_data["projectTitle"],
                "project_description": form_data["projectDescription"],
                "sent_to_client": datetime.strptime(form_data["sentDate"], "%Y-%m-%d"),
                "job": job,
                "uploaded_by": self.request.user,
                "category": category,
            }
            category
            files = request.FILES.getlist("files")
            location = project_documentation_files_dir
            fs = OverwriteStorageProjectDocumentation(location=location)

            project_obj = ProjectDocumentationUpload.objects.get_or_create(**data)

            for file in files:
                fs.save(
                    os.path.join(
                        "{}".format(str(job.id)),
                        "{}".format(str(project_obj[0].id)),
                        file.name,
                    ),
                    file,
                )

            file_path = os.path.join(
                settings.MEDIA_ROOT,
                project_documentation_files_dir,
                str(job.id),
                str(project_obj[0].id),
            )

            shutil.make_archive(
                "{}".format(file_path, str(project_obj[0].id)), "zip", file_path
            )
            # if self.exists(zipped_file):
            #     os.remove(os.path.join(settings.MEDIA_ROOT, "project_documentation", zipped_file))

            return Response(status=status.HTTP_201_CREATED)
        except Exception as e:
            raise e

    def schedule(self, request, pk=None):

        report_id = request.data["reportID"]

        

        

        # Format dates if they're in the wrong format
        for date_field in ["start_date", "end_date"]:
            if date_field in request.data and "/" in request.data[date_field]:
                date_parts = request.data[date_field].split("/")
                request.data[date_field] = (
                    f"{date_parts[2]}-{date_parts[0]}-{date_parts[1]}"
                )

        project_doc = ProjectDocumentationUpload.objects.get(id=report_id)
        assignee = User.objects.get(id=request.data["assignee"])

        project_doc.completion_status = 0
        project_doc.start_date = request.data["start_date"]
        project_doc.end_date = request.data["end_date"]
        project_doc.assignee = assignee

        project_doc.save()
        notification_data = []
        context = {
            "name": assignee.name,
            "link": f"{request.build_absolute_uri(reverse('view-project-documentation'))}?job_number={project_doc.job.job_number}",
            "job_number": project_doc.job.job_number,
            "call_to_action": "View Assigned Report Upload Task",
        }

        notification_data.append(
            {
                "user_to_notify": assignee,
                "notification_type": TASK_ASSIGNED,
                "email_subject": "New schedule created for report upload",
                "email_context": context,
            }
        )
        # Bulk create notifications
        with transaction.atomic():
            notifications = Notification.objects.bulk_create(
                [Notification(**data) for data in notification_data]
            )

        # Send emails in bulk
        send_bulk_emails(notification_data)
        
        

        return Response(
            {"message": "Schedule created successfully"}, status=status.HTTP_200_OK
        )

    def start(self, request, pk=None):
        report_id = request.data["reportID"]
        project_doc = ProjectDocumentationUpload.objects.get(id=report_id)
        project_doc.completion_status = 1
        project_doc.save()
        return Response(status=status.HTTP_200_OK)

    def complete(self, request, pk=None):
        report_id = request.data["reportID"]
        project_doc = ProjectDocumentationUpload.objects.get(id=report_id)
        project_doc.completion_status = 2
        project_doc.save()
        return Response(status=status.HTTP_200_OK)


from django.contrib.auth.models import Permission


class ViewProjectDocumentation(ListView):
    model = DataUpload
    template_name = "view_project_documentation.html"

    def dispatch(self, request, *args, **kwargs):
        job_number = self.request.GET.get("job_number")
        if job_number is None:
            raise Http404
        self.job = get_object_or_404(Job, job_number=job_number)
        return super(ViewProjectDocumentation, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(ViewProjectDocumentation, self).get_context_data(**kwargs)
        context["job"] = self.job
        return context

    def get_queryset(self):

        try:
            project_documentation_files_dir = os.path.join(
                settings.MEDIA_ROOT,
                "project_documentation",
            )

            job_number = Job.objects.get(id=self.job.id)
            if self.request.user.groups.filter(name="Regional Admin").exists():

                project_obj = ProjectDocumentationUpload.objects.filter(job=self.job.id)
            else:
                project_obj = ProjectDocumentationUpload.objects.filter(
                    Q(job=self.job.id)
                    & Q(job__organization=self.request.user.organization)
                )

            data = {}
            project_files = {}
            ids = []

            for obj in project_obj:

                ids.append(obj.id)
                data[obj.id] = {
                    "id": obj.id,
                    "project_description": obj.project_description,
                    "project_title": obj.project_title,
                    "uploaded_by": obj.uploaded_by,
                    "sent_to_client": obj.sent_to_client,
                    "category": obj.report.name,
                    "is_uplaoded": obj.is_uploaded,
                    "job_id": obj.job_id,
                    "completion_status": obj.completion_status,
                    "assignee": obj.assignee,
                }

            users_obj = User.objects.filter()
            users_serializer = UserSerializer(users_obj, many=True)

            for key, val in data.items():
                try:
                    zip_path = os.path.join(
                        project_documentation_files_dir, str(obj.job_id), f"{key}.zip"
                    )
                    # Open the zip file
                    with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        # List all the files in the zip archive
                        zip_files = zip_ref.namelist()
                        # Check if the zip archive has files
                        if zip_files:
                            for file in zip_files:
                                # Append files to the project_files dictionary under the corresponding key
                                if key in project_files.keys():
                                    project_files[key].append(file)
                                else:
                                    project_files[key] = [file]
                            # Update the 'data' dictionary with the files found in the zip archive for the current key
                            data[key]["files"] = project_files[key]
                except:

                    context = {"job_number": job_number, "data": ""}
                context = {
                    "job_number": job_number,
                    "data": data,
                    "users": users_serializer.data,
                }
            
            

            return context
        except Exception as e:
            print(str(e), "--------------")

            return Response(str(e))


def download_project_documentation(request):
    project_documentation_files_dir = os.path.join(
        settings.MEDIA_ROOT,
        "project_documentation",
    )

    project_documentation_id = request.build_absolute_uri().split("?")[-1]
    project_obj = ProjectDocumentationUpload.objects.get(
        id=int(project_documentation_id)
    )

    job_number = request.build_absolute_uri().split("?")[-2]
    job = Job.objects.get(job_number=job_number)

    # Build the path to the zip file
    zip_base_path = os.path.join(
        settings.MEDIA_ROOT, "project_documentation", str(job.id)
    )
    zip_file_name = (
        f"{project_obj.id}.zip"  # Assuming the zip file is named after the job ID
    )
    zip_path = os.path.join(zip_base_path, zip_file_name)

    # Check if the file exists
    if not os.path.exists(zip_path):
        raise Http404("Zip file does not exist")

    # Open the file for reading in binary mode
    with open(zip_path, "rb") as fh:
        response = HttpResponse(FileWrapper(fh), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{zip_file_name}"'
        return response


class ReportsViewSet(viewsets.ModelViewSet):
    """
    View for list, create, update, delete reports
    """

    queryset = Report.objects.all()
    serializer_class = ReportDetailSerializer
    template_name = "report_categories.html"
    paginate_by = 10

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ReportDetailSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return ReportCreateSerializer
        return ReportDetailSerializer

    def get_queryset(self):
        queryset = Report.objects.all()
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(created_by__email__icontains=search_query)
                | Q(updated_by__email__icontains=search_query)
            )
        return queryset

    def retrieve(self, request, pk=None):
        queryset = Report.objects.all()
        report = get_object_or_404(queryset, pk=pk)
        serializer = self.get_serializer(report)

        if request.accepted_renderer.format == "html":
            return render(
                request, self.detail_template_name, {"report": serializer.data}
            )
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = request.GET.get("page", 1)
        paginator = Paginator(queryset, self.paginate_by)

        try:
            reports = paginator.page(page)
        except PageNotAnInteger:
            reports = paginator.page(1)
        except EmptyPage:
            reports = paginator.page(paginator.num_pages)

        serializer = self.get_serializer(reports, many=True)

        context = {
            "reports": serializer.data,
            "page_obj": reports,
            "is_paginated": reports.has_other_pages(),
            "paginator": paginator,
        }

        if request.accepted_renderer.format == "html":
            return render(request, self.template_name, context)
        return Response(context)

    def create(self, request, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=self.request.user)
            self.perform_create(serializer)
            if request.accepted_renderer.format == "html":
                return render(
                    request, self.template_name, {"reports": self.get_queryset()}
                )
            return Response(serializer.data, status=201)

        if request.accepted_renderer.format == "html":
            return render(request, self.template_name, {"errors": serializer.errors})

        return Response(serializer.errors, status=400)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer_class(
            instance, data=request.data, partial=partial
        )

        if serializer.is_valid():
            serializer.save(updated_by=self.request.user)
            self.perform_update(serializer)
            if request.accepted_renderer.format == "html":
                return render(
                    request, self.template_name, {"reports": self.get_queryset()}
                )
            return Response(serializer.data)

        if request.accepted_renderer.format == "html":
            return render(request, self.template_name, {"errors": serializer.errors})
        return Response(serializer.errors, status=400)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        if request.accepted_renderer.format == "html":
            return render(request, self.template_name, {"reports": self.get_queryset()})
        return Response(status=204)


# class ReportsViewSet(viewsets.ModelViewSet):
#     """
#     View for list, create, update, delete roles
#     """

#     queryset = Report.objects.all()

#     def get_serializer_class(self):
#         if self.action == "list":
#             return ReportSerializer
#         return ReportSerializer

#     def list(self, request, *args, **kwargs):
#         if request.accepted_renderer.format == "html":
#             roles = Report.objects.all()
#             return Response({"roles": roles}, template_name="categories.html")
#         return super(ReportsViewSet, self).list(request)

#     def delete(self, request, *args, **kwargs):
#         pass


class GetSingleProjectDocumentation(APIView):
    def get(self, request, pk=None):
        project = ProjectDocumentationUpload.objects.get(id=pk)
        data = {
            "project_title": project.project_title,
            "project_description": project.project_description,
            # "category": project.category.name,
            "date": project.sent_to_client,
        }

        return Response(data, status=status.HTTP_200_OK)

    # @action(detail=True, methods=["put"])
    def put(self, request, pk=None):
        try:
            project = ProjectDocumentationUpload.objects.get(id=pk)
            form_data = json.loads(request.data["formData"])
            category = Category.objects.get(id=int(form_data["selectedId"]))

            user = CustomUser.objects.filter(email=self.request.user.email)

            data = {
                "project_title": form_data["projectTitle"],
                "project_description": form_data["projectDescription"],
                "sent_to_client": datetime.strptime(form_data["sentDate"], "%Y-%m-%d"),
                "uploaded_by": user[0].id,
                # "category": category.id,
                "job": project.job.id,
            }

            serializer = ProjectDocumentationUploadSerializer(project, data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            project_id = project.id
            project_documentation_files_dir = os.path.join(
                settings.MEDIA_ROOT,
                "project_documentation",
            )
            full_path = os.path.join(
                project_documentation_files_dir, str(project.job.id), str(project_id)
            )
            files = request.FILES.getlist("files")
            location = full_path
            fs = OverwriteProjectDocumentationStorage(location=location)

            for file in files:
                fs.save(
                    os.path.join(file.name),
                    file,
                )

            shutil.make_archive(
                "{}".format(full_path, str(project.job.id)), "zip", full_path
            )

            return Response("updated", status=status.HTTP_200_OK)

        except Exception as e:
            print(e),
            return Response(str(e))


class GetSingleReport(APIView):
    def put(self, request, pk=None):
        try:
            category = Report.objects.get(id=pk)
            user = CustomUser.objects.filter(email=self.request.user.email)
            data = {
                "name": request.data["name"],
                "external": request.data["external"],
                "internal": request.data["internal"],
                "created_by": user[0].id,
            }

            serializer = ReportSerializer(category, data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response("updated", status=status.HTTP_200_OK)

        except Exception as e:
            print(e),
            return Response(str(e))


from labs.models import UnitCost

from invoicing.models import Invoice, InvoiceItem


def apply_new_prices(self):
    tests = JobTest.objects.filter(job__job_number__icontains="2023")

    unit_costs = UnitCost.objects.filter(Q(from_date="2023") & Q(from_date="2024"))

    for test in tests:
        test_id = test.test_id

        try:
            unit_cost_obj = UnitCost.objects.filter(
                Q(from_date="2023") & Q(to_date="2024")
            ).filter(test_id=test_id)
            test.test_id = UnitCost.objects.get(id=unit_cost_obj[0].id)
            test.save()

            invoice_obj = Invoice.objects.get(job_id=test.job.id)

            invoice_items = InvoiceItem.objects.filter(invoice_id=invoice_obj.id)

            # for invoice_item in invoice_items:
            #     invoice_unit_cost =  UnitCost.objects.filter(Q (from_date='2023') & Q (to_date='2024')).filter(test__name=invoice_item.description)

            #     invoice_item.unit_cost = invoice_unit_cost[0].unit_cost
            #     invoice_item.test_id =  UnitCost.objects.get(id=invoice_unit_cost[0].id)
            #     invoice_item.save()

        except Exception as e:
            unit_cost_obj = UnitCost.objects.filter(
                Q(from_date="2023") & Q(to_date="2024")
            ).filter(id=test_id)
            test.test_id = UnitCost.objects.get(id=unit_cost_obj[0].id)
            test.save()
            invoice_obj = Invoice.objects.get(job_id=test.job.id)

            invoice_items = InvoiceItem.objects.filter(invoice_id=invoice_obj.id)

            for invoice_item in invoice_items:
                invoice_unit_cost = UnitCost.objects.filter(
                    Q(from_date="2023") & Q(to_date="2024")
                ).filter(test__name=invoice_item.description)

                invoice_item.unit_cost = invoice_unit_cost[0].unit_cost
                invoice_item.test_id = UnitCost.objects.get(id=invoice_unit_cost[0].id)
                invoice_item.save()

    return HttpResponse("hey")


def update_invoice_items(self):
    invoice_items_2023 = InvoiceItem.objects.filter(
        invoice__job__job_number__icontains=2023
    )
    invoice_items_2022 = InvoiceItem.objects.exclude(
        invoice__job__job_number__icontains=2023
    )

    for invoice_item in invoice_items_2022:
        invoice_unit_cost = UnitCost.objects.filter(
            Q(from_date="2022") & Q(to_date="2023")
        ).filter(test__name=invoice_item.description)

        # invoice_item.test_id =  UnitCost.objects.get(id=invoice_unit_cost[0].id)
        invoice_item.save()

    for invoice_item in invoice_items_2023:
        invoice_unit_cost = UnitCost.objects.filter(
            Q(from_date="2023") & Q(to_date="2024")
        ).filter(test__name=invoice_item.description)

        invoice_item.unit_cost = invoice_unit_cost[0].unit_cost
        # invoice_item.test_id =  UnitCost.objects.get(id=invoice_unit_cost[0].id)
        invoice_item.save()

    return HttpResponse("hey")


def page_not_found_view(request, exception):
    return render(request, "404.html", status=404)




class ConsolidatedData(viewsets.ModelViewSet):
    permission = [AllowAny]

    def instruments(self, request):
        # Check if user is Regional Admin
        is_regional_admin = request.user.groups.filter(name="Regional Admin").exists()

        # Base queryset with organization filtering
        if is_regional_admin:
            tasks = JobTest.objects.all().select_related(
                "job", "test__test", "test__test__instrument", "assignee"
            )
            filter_organization = None
        else:
            tasks = JobTest.objects.filter(
                job__organization=request.user.organization
            ).select_related(
                "job", "test__test", "test__test__instrument", "assignee"
            )
            filter_organization = request.user.organization

        # Organization filter (only for Regional Admins)
        organization_filter = request.GET.get("organization", "").strip()
        if is_regional_admin and organization_filter:
            tasks = tasks.filter(job__organization_id=organization_filter)

        # Search functionality
        search_query = request.GET.get("search", "").strip()
        if search_query:
            tasks = tasks.filter(
                Q(job__job_number__icontains=search_query) |
                Q(job__country__icontains=search_query) |
                Q(job__region__icontains=search_query) |
                Q(job__project__icontains=search_query) |
                Q(job__site__icontains=search_query) |
                Q(job__scientist_name__icontains=search_query) |
                Q(job__scientist_email__icontains=search_query)
            )

        # Filter by instrument name
        instrument_name_filter = request.GET.get("instrument_name", "").strip()
        if instrument_name_filter:
            tasks = tasks.filter(test__test__instrument__name__icontains=instrument_name_filter)

        # Filter by data upload status
        data_upload_filter = request.GET.get("data_upload_status", "").strip()
        if data_upload_filter:
            if data_upload_filter == "completed":
                tasks = tasks.filter(data_upload_status=True)
            elif data_upload_filter == "not_completed":
                tasks = tasks.filter(data_upload_status=False)

        # Date filtering
        date_field = request.GET.get("date_field", "")
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")

        if date_field and (date_from or date_to):
            date_filters = {}

            if date_from:
                try:
                    from_date = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
                    date_filters[f"{date_field}__gte"] = from_date
                except ValueError:
                    pass

            if date_to:
                try:
                    to_date = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
                    date_filters[f"{date_field}__lte"] = to_date
                except ValueError:
                    pass

            if date_filters:
                tasks = tasks.filter(**date_filters)

        # Sorting
        sort_field = request.GET.get("sort", "-job__created_at")
        sort_direction = request.GET.get("sort_direction", "desc")

        valid_sort_fields = {
            "job_number": "job__job_number",
            "instrument_name": "test__test__instrument__name",
            "created_at": "job__created_at",
        }

        if sort_field in valid_sort_fields:
            sort_field_name = valid_sort_fields[sort_field]
            if sort_direction == "desc":
                sort_field_name = f"-{sort_field_name}"
            tasks = tasks.order_by(sort_field_name)
        else:
            tasks = tasks.order_by("-job__created_at")

        # Get filter options
        filter_options = self.get_instrument_filter_options(
            organization=filter_organization,
            is_regional_admin=is_regional_admin,
            selected_organization_id=organization_filter if organization_filter else None
        )

        # Pagination
        page_number = request.GET.get("page_number", 1)
        paginator = Paginator(tasks, per_page=30)
        page_object = paginator.get_page(int(page_number))
        page_object.adjusted_elided_pages = paginator.get_elided_page_range(
            int(page_number)
        )

        # Group by job and then by instrument
        tasks_dict = {}
        for x in page_object:
            job_tests_data = JobTestsSerializer(x)
            data = job_tests_data.data

            job_number = data.get("job", {}).get("job_number", "Unknown")

            # Get instrument object and check all_jobs field
            instrument_obj = None
            instrument_name = "No Instrument"
            instrument_all_jobs = False

            try:
                # Get the instrument from the model object
                if hasattr(x, 'test') and hasattr(x.test, 'test') and hasattr(x.test.test, 'instrument'):
                    instrument_obj = x.test.test.instrument
                    if instrument_obj:
                        instrument_name = instrument_obj.name
                        # Check if the instrument has all_jobs field set to True
                        instrument_all_jobs = getattr(instrument_obj, 'all_jobs', False)
            except (AttributeError, TypeError, KeyError) as e:
                # If anything goes wrong, default to "No Instrument"
                instrument_name = "No Instrument"
                instrument_all_jobs = False

            # Skip this instrument if all_jobs is True
            if instrument_all_jobs:
                continue

            if job_number not in tasks_dict:
                tasks_dict[job_number] = {}

            if instrument_name not in tasks_dict[job_number]:
                tasks_dict[job_number][instrument_name] = {
                    "tests": [],
                    "all_jobs": instrument_all_jobs,
                    "data_upload_completed": True  # Start as True, will be set to False if any test is incomplete
                }

            # Add test data
            tasks_dict[job_number][instrument_name]["tests"].append(data)

            # Update data_upload_completed status - if any test is not completed, set to False
            if not data.get("data_upload_status", False):
                tasks_dict[job_number][instrument_name]["data_upload_completed"] = False

        # Get current filter values for template
        current_filters = {
            "search": search_query,
            "instrument_name": instrument_name_filter,
            "organization": organization_filter if is_regional_admin else "",
            "data_upload_status": data_upload_filter,
            "date_field": date_field,
            "date_from": date_from,
            "date_to": date_to,
            "sort": request.GET.get("sort", ""),
            "sort_direction": sort_direction,
        }

        return Response(
            {
                "context": tasks_dict,
                "page_obj": page_object,
                "filter_options": filter_options,
                "current_filters": current_filters,
                "is_regional_admin": is_regional_admin,
            },
            template_name="consolidated_data/instruments.html",
        )

    def get_instrument_filter_options(self, organization=None, is_regional_admin=False, selected_organization_id=None):
        """Get filter options for instruments based on organization"""

        # If a specific organization is selected (by Regional Admin), use that for filtering
        if is_regional_admin and selected_organization_id:
            job_filter = Q(job__organization_id=selected_organization_id)
        elif organization:
            # Regular user - use their organization
            job_filter = Q(job__organization=organization)
        else:
            # Regional Admin with no organization selected - show all
            job_filter = Q()

        # Get unique instrument names (filtered by organization)
        instrument_names = list(
            JobTest.objects.filter(job_filter)
            .values_list("test__test__instrument__name", flat=True)
            .distinct()
            .order_by("test__test__instrument__name")
        )

        # Get organizations (only for Regional Admins)
        organizations = []
        if is_regional_admin:
            organizations = list(
                Organization.objects.all()
                .values("id", "name")
                .order_by("name")
            )

        # Date field options
        date_fields = [
            ("job__created_at", "Job Created Date"),
            ("job__samples_received_on", "Samples Received Date"),
            ("start_date", "Start Date"),
            ("end_date", "End Date"),
            ("job__testing_authorized_at", "Testing Authorized Date"),
            ("job__samples_uploaded_at", "Samples Uploaded Date"),
        ]

        # Data upload status options
        data_upload_statuses = [
            ("completed", "Completed"),
            ("not_completed", "Not Completed"),
        ]

        return {
            "instrument_names": instrument_names,
            "organizations": organizations,
            "date_fields": date_fields,
            "data_upload_statuses": data_upload_statuses,
        }


class ConsolidatedSchedules(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    PAGINATION_SIZE = 10

    @action(detail=False, methods=["get"])
    def download_csv(self, request):
        """Download filtered results as CSV"""

        # Check if user is Regional Admin
        is_regional_admin = request.user.groups.filter(name="Regional Admin").exists()

        # Apply the same filtering logic as the main view
        if is_regional_admin:
            tasks = JobTest.objects.all().select_related(
                "job", "test__test", "test__test__instrument", "assignee"
            )
        else:
            tasks = JobTest.objects.filter(
                job__organization=request.user.organization
            ).select_related(
                "job", "test__test", "test__test__instrument", "assignee"
            )

        # Organization filter (only for Regional Admins)
        organization_filter = request.GET.get("organization", "").strip()
        if is_regional_admin and organization_filter:
            tasks = tasks.filter(job__organization_id=organization_filter)

        # Apply all the same filters
        search_query = request.GET.get("search", "").strip()
        if search_query:
            tasks = tasks.filter(
                Q(job__job_number__icontains=search_query) |
                Q(job__country__icontains=search_query) |
                Q(job__region__icontains=search_query) |
                Q(job__project__icontains=search_query) |
                Q(job__site__icontains=search_query) |
                Q(job__scientist_name__icontains=search_query) |
                Q(job__scientist_email__icontains=search_query)
            )

        test_name_filter = request.GET.get("test_name", "").strip()
        if test_name_filter:
            tasks = tasks.filter(test__test__name__icontains=test_name_filter)

        completion_status_filter = request.GET.get("completion_status", "").strip()
        if completion_status_filter:
            tasks = tasks.filter(completion_status=completion_status_filter)

        # Date filtering
        date_field = request.GET.get("date_field", "")
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")

        if date_field and (date_from or date_to):
            date_filters = {}
            
            if date_from:
                try:
                    from_date = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
                    date_filters[f"{date_field}__gte"] = from_date
                except ValueError:
                    pass
                    
            if date_to:
                try:
                    to_date = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
                    date_filters[f"{date_field}__lte"] = to_date
                except ValueError:
                    pass
            
            if date_filters:
                tasks = tasks.filter(**date_filters)

        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="consolidated_schedules_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Job Number',
            'Test Name',
            'Instrument',
            'Completion Status',
            'Country',
            'Region',
            'Project',
            'Site',
            'Scientist Name',
            'Scientist Email',
            'Start Date',
            'End Date',
            'Samples Received On',
            'Created At',
        ])

        # Write data rows
        for task in tasks:
            completion_status_display = {
                0: 'Not started',
                1: 'Pending',
                2: 'Completed'
            }.get(task.completion_status, 'Unknown')
            # import pdb
            # pdb.set_trace()

            writer.writerow([
                task.job.job_number,
                task.test.test.name if task.test and task.test.test else '',
                task.test.test.instrument.name if task.test and task.test.test and task.test.test.instrument else '',
                completion_status_display,
                task.job.country or '',
                task.job.region or '',
                task.job.project or '',
                task.job.site or '',
                task.job.scientist_name or '',
                task.job.scientist_email or '',
                task.start_date.strftime('%Y-%m-%d') if task.start_date else '',
                task.end_date.strftime('%Y-%m-%d') if task.end_date else '',
                task.job.samples_received_on.strftime('%Y-%m-%d') if task.job.samples_received_on else '',
                task.job.created_at.strftime('%Y-%m-%d %H:%M:%S') if task.job.created_at else '',
            ])

        return response

    @action(detail=False, methods=["get"])
    def instruments(self, request):
        # Check if user is Regional Admin
        is_regional_admin = request.user.groups.filter(name="Regional Admin").exists()

        # Base queryset with organization filtering
        if is_regional_admin:
            tasks = JobTest.objects.all().select_related(
                "job", "test__test", "test__test__instrument", "assignee"
            )
            filter_organization = None
        else:
            tasks = JobTest.objects.filter(
                job__organization=request.user.organization
            ).select_related(
                "job", "test__test", "test__test__instrument", "assignee"
            )
            filter_organization = request.user.organization

        # Organization filter (only for Regional Admins)
        organization_filter = request.GET.get("organization", "").strip()
        if is_regional_admin and organization_filter:
            tasks = tasks.filter(job__organization_id=organization_filter)

        # Search functionality
        search_query = request.GET.get("search", "").strip()
        if search_query:
            tasks = tasks.filter(
                Q(job__job_number__icontains=search_query) |
                Q(job__country__icontains=search_query) |
                Q(job__region__icontains=search_query) |
                Q(job__project__icontains=search_query) |
                Q(job__site__icontains=search_query) |
                Q(job__scientist_name__icontains=search_query) |
                Q(job__scientist_email__icontains=search_query)
            )

        # Filter by lab test name
        test_name_filter = request.GET.get("test_name", "").strip()
        if test_name_filter:
            tasks = tasks.filter(test__test__name__icontains=test_name_filter)

        # Filter by completion status
        completion_status_filter = request.GET.get("completion_status", "").strip()
        if completion_status_filter:
            tasks = tasks.filter(completion_status=completion_status_filter)

        # Date filtering
        date_field = request.GET.get("date_field", "")
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")

        if date_field and (date_from or date_to):
            date_filters = {}
            
            if date_from:
                try:
                    from_date = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
                    date_filters[f"{date_field}__gte"] = from_date
                except ValueError:
                    pass
                    
            if date_to:
                try:
                    to_date = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
                    date_filters[f"{date_field}__lte"] = to_date
                except ValueError:
                    pass
            
            if date_filters:
                tasks = tasks.filter(**date_filters)

        # Sorting
        sort_field = request.GET.get("sort", "-job__created_at")
        sort_direction = request.GET.get("sort_direction", "desc")
        
        valid_sort_fields = {
            "job_number": "job__job_number",
            "test_name": "test__test__name", 
            "completion_status": "completion_status",
            "created_at": "job__created_at",
            "start_date": "start_date",
            "end_date": "end_date",
            "samples_received_on": "job__samples_received_on",
            "scientist_name": "job__scientist_name",
            "country": "job__country",
            "region": "job__region",
            "project": "job__project",
            "site": "job__site",
        }
        
        if sort_field in valid_sort_fields:
            sort_field_name = valid_sort_fields[sort_field]
            if sort_direction == "desc":
                sort_field_name = f"-{sort_field_name}"
            tasks = tasks.order_by(sort_field_name)
        else:
            tasks = tasks.order_by("-job__created_at")

        # Get filter options - pass selected organization for cascading filters
        filter_options = self.get_filter_options(
            organization=filter_organization,
            is_regional_admin=is_regional_admin,
            selected_organization_id=organization_filter if organization_filter else None
        )

        # Pagination
        page_number = request.GET.get("page_number", 1)
        paginator = Paginator(tasks, per_page=30)
        page_object = paginator.get_page(int(page_number))
        page_object.adjusted_elided_pages = paginator.get_elided_page_range(
            int(page_number)
        )

        # Group tasks by job number
        tasks_dict = {}
        for x in page_object:
            job_tests_data = JobTestsSerializer(x)
            if job_tests_data.data["job"]["job_number"] not in tasks_dict:
                tasks_dict[job_tests_data.data["job"]["job_number"]] = []
            tasks_dict[job_tests_data.data["job"]["job_number"]].append(
                job_tests_data.data
            )

        # Get current filter values for template
        current_filters = {
            "search": search_query,
            "test_name": test_name_filter,
            "organization": organization_filter if is_regional_admin else "",
            "completion_status": completion_status_filter,
            "date_field": date_field,
            "date_from": date_from,
            "date_to": date_to,
            "sort": request.GET.get("sort", ""),
            "sort_direction": sort_direction,
        }

        return Response(
            {
                "context": tasks_dict,
                "page_obj": page_object,
                "filter_options": filter_options,
                "current_filters": current_filters,
                "is_regional_admin": is_regional_admin,
            },
            template_name="consolidated_data/schedules.html",
        )
    
    
    
    def get_filter_options(self, organization=None, is_regional_admin=False, selected_organization_id=None):
        """Get filter options based on organization"""

        # If a specific organization is selected (by Regional Admin), use that for filtering
        if is_regional_admin and selected_organization_id:
            job_filter = Q(job__organization_id=selected_organization_id)
        elif organization:
            # Regular user - use their organization
            job_filter = Q(job__organization=organization)
        else:
            # Regional Admin with no organization selected - show all
            job_filter = Q()

        # Get unique test names (filtered by organization)
        test_names = list(
            JobTest.objects.filter(job_filter)
            .values_list("test__test__name", flat=True)
            .distinct()
            .order_by("test__test__name")
        )

        # Get organizations (only for Regional Admins)
        organizations = []
        if is_regional_admin:
            organizations = list(
                Organization.objects.all()
                .values("id", "name")
                .order_by("name")
            )

        # Date field options
        date_fields = [
            ("job__created_at", "Job Created Date"),
            ("job__samples_received_on", "Samples Received Date"),
            ("start_date", "Start Date"),
            ("end_date", "End Date"),
            ("job__testing_authorized_at", "Testing Authorized Date"),
            ("job__samples_uploaded_at", "Samples Uploaded Date"),
        ]

        # Completion status options
        completion_statuses = [
            ("0", "Not started"),
            ("1", "Pending"),
            ("2", "Completed"),
        ]

        return {
            "test_names": test_names,
            "organizations": organizations,
            "date_fields": date_fields,
            "completion_statuses": completion_statuses,
        }

# class ConsolidatedSchedules(viewsets.ModelViewSet):
#     permission_classes = [IsAuthenticated]
#     PAGINATION_SIZE = 10

#     @action(detail=False, methods=["get"])
#     def instruments(self, request):
#         tasks_dict = {}

#         # for job in jobs:
#         if request.user.groups.filter(name="Regional Admin").exists():
#             tasks = (
#                 JobTest.objects.all().select_related("job").order_by("-job__created_at")
#             )
#         else:
#             tasks = (
#                 JobTest.objects.filter(job__organization=self.request.user.organization)
#                 .select_related("job")
#                 .order_by("-job__created_at")
#             )

#         tasks_dict = {}

#         page_number = request.GET.get("page_number")

#         if page_number == None:
#             page_number = 1
#         paginator = Paginator(tasks, per_page=30)
#         page_object = paginator.get_page(int(page_number))
#         page_object.adjusted_elided_pages = paginator.get_elided_page_range(
#             int(page_number)
#         )
#         context = {"page_obj": page_object}
#         # import pdb
#         # pdb.set_trace()

#         for x in page_object:
#             job_tests_data = JobTestsSerializer(x)
#             if job_tests_data.data["job"]["job_number"] not in tasks_dict:
#                 tasks_dict[job_tests_data.data["job"]["job_number"]] = []
#             tasks_dict[job_tests_data.data["job"]["job_number"]].append(
#                 job_tests_data.data
#             )

#         return Response(
#             {"context": tasks_dict, "page_obj": page_object},
#             template_name="consolidated_data/schedules.html",
#         )



class ProjectDocumentationCompletionAPIview(APIView):
    def put(self, request, pk):
        job = Job.objects.get(job_number=pk)
        upload_status = request.GET["status"]

        if upload_status == "incomplete":
            job.project_documentation_uploaded = False
        elif upload_status == "complete":
            job.project_documentation_uploaded = True

        job.save()

        return Response(status=status.HTTP_200_OK)


from archives.models import Archive


class ArchivingAPIView(APIView):
    def put(self, request, pk):
        job = Job.objects.get(job_number=pk)
        upload_status = request.GET["status"]

        if upload_status == "incomplete":
            job.is_archive_uploaded = False
        elif upload_status == "complete":
            job.is_archive_uploaded = True

        job.save()

        return Response(status=status.HTTP_200_OK)


from django.shortcuts import redirect


class DataAPIView(APIView):
    def get(self, request, pk):
        status = request.GET["status"]
        instruemnt_id = request.GET["instruemnt_id"]
        job_test = JobTest.objects.filter(job=pk).filter(
            test__test__instrument_id=instruemnt_id
        )

        if status == "true":
            job_test.update(data_upload_status=True)
        elif status == "false":
            job_test.update(data_upload_status=False)
            
        return redirect(request.META["HTTP_REFERER"])


class ReportUpdateStatusAPIView(APIView):
    def get(self, request, pk):
        status = request.GET["status"]
        report_id = request.GET["report_id"]

        report = ProjectDocumentationUpload.objects.get(id=report_id)
        if status == "false":
            report.is_uploaded = False
        elif status == "true":
            report.is_uploaded = True
        report.save()

        return redirect(request.META["HTTP_REFERER"])


# def add_pxrf(self):
#     for jn in data_list:
#         job_number = "{}-{}-{}".format( jn[:3] , jn[3:6], jn[6:])
#         job = Job.objects.get(job_number=job_number)
#         ut=UnitCost.objects.get(id=50)
#         JobTest.objects.create(job_id=job.id, test_id=ut.id)

#         return HttpResponse("hry")


class gETtESTS(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        invoice_items = InvoiceItem.objects.filter()

        jobs_2023 = (
            Job.objects.filter(job_number__icontains="2023")
            .exclude(job_number__icontains="ICR-11-2023")
            .order_by("-id")
        )
        jobs_2022 = (
            Job.objects.filter(job_number__icontains="2022")
            .exclude(job_number__icontains="ICR-11-2023")
            .order_by("-id")
        )
        try:
            for job in jobs_2023:
                invoices = Invoice.objects.filter(job=job.id)

                for invoice in invoices:
                    invoice_items = InvoiceItem.objects.filter(invoice_id=invoice.id)

                    for invoice_item in invoice_items:
                        try:
                            if (
                                invoice_item.description
                                == "Mid Infrared Spectroscopy using the the Alpha Spectrometer for  soils/plants/manure/dry compost"
                            ):
                                desc = "Mid Infrared Spectroscopy using the Alpha Spectrometer for  soils/plants/manure/dry compost"
                            elif (
                                invoice_item.description
                                == "Laser Diffraction Paticle size Analysys-Soil Particle Size Distribution or Texture"
                            ):
                                desc = "ldpsa"
                            else:
                                desc = invoice_item.description
                            unit_cost = UnitCost.objects.get(
                                Q(test__name=desc) & Q(from_date__icontains="2023")
                            )
                            invoice_item.test_id = unit_cost.id
                            invoice_item.save()
                        except UnitCost.DoesNotExist:
                            if (
                                invoice_item.description
                                == "Mid Infrared Spectroscopy using the the Alpha Spectrometer for  soils/plants/manure/dry compost"
                            ):
                                desc = "Mid Infrared Spectroscopy using the Alpha Spectrometer for  soils/plants/manure/dry compost"
                            else:
                                desc = invoice_item.description
                            unit_cost = UnitCost.objects.get(
                                Q(test__description=desc)
                                & Q(from_date__icontains="2023")
                            )
                            invoice_item.test_id = unit_cost.id
                            invoice_item.save()

            return Response("hey")

        except Exception as e:
            print(str(e), "--------------")
            return Response(
                {
                    "mm": str(e),
                }
            )


from django.db import IntegrityError
from django.db.models import F
from django.db import transaction


class JobSampleInfoo(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        jobs = Job.objects.filter(
            Q(job_number__icontains="2014")
            | Q(job_number__icontains="2015")
            | Q(job_number__icontains="2016")
            | Q(job_number__icontains="2017")
            | Q(job_number__icontains="2018")
            | Q(job_number__icontains="2019")
            | Q(job_number__icontains="2020")
            | Q(job_number__icontains="2021")
        )

        for job in jobs:
            job_obj = Job.objects.get(id=job.id)
            JobSampleStatus.objects.get_or_create(
                processed=False, dry=True, other=False, job_id=job_obj.id
            )
            # sample=JobSampleStatus.objects.get(job=job_obj.id)
            # sample.delete()

            # data  = {
            #     "plant": '',
            #     "soil": '',
            #     "other": 'Other',
            #     "fertilizer": ''
            # }

        return Response("hey")

    def get(self, request):
        jobs = Job.objects.filter(
            Q(scientist_email__exact="") & Q(scientist_name__exact="")
            | Q(scientist_email__exact="")
        )
        user = CustomUser.objects.get(email="salmanyagakaws@gmail.com")

        # for job in jobs:
        #     job.scientist_name = 'Dummy scientist'

        #     job.scientist_email = 'salmanyagakaws@gmail.com'
        #     job.scientist_id = user
        #     job.save()

        jobs2 = Job.objects.filter(
            Q(job_number__icontains="2014")
            | Q(job_number__icontains="2015")
            | Q(job_number__icontains="2016")
            | Q(job_number__icontains="2017")
            | Q(job_number__icontains="2018")
            | Q(job_number__icontains="2019")
            | Q(job_number__icontains="2020")
            | Q(job_number__icontains="2021")
        )

        for job in jobs2:
            jobs_test = JobTest.objects.filter(job_id=job.id)
            for test in jobs_test:
                test.data_upload_status = True
                test.save()

            # project_documenentation =  ProjectDocumentationUpload.objects.filter(job=job.id)
            # if project_documenentation:
            #     for pp in project_documenentation:

            #         pp.is_uploaded = True
            #         pp.save()
            # else:
            #     continue

        # for job in jobs2:
        #     samples = Sample.objects.filter(job_id=job.pk)
        #     if samples:
        #         if job.sampling_design == Job.LDSF:
        #             samplesldsfdetails = samples.select_related("sampleldsfdetail")

        #         else:
        #             fields = CustomField.objects.filter(jobs__in=[job]).values_list(
        #                 "label", flat=True
        #             )
        #             d = {
        #                 field: Subquery(
        #                     CustomFieldValue.objects.filter(
        #                         field__label=field, sample_id=OuterRef("pk")
        #                     ).values("value")
        #                 )
        #                 for field in fields
        #             }
        #             samples = samples.annotate(**d)

        #             page_obj = samples.values("number", "job", "barcode", "qr_code", *fields)

        #             samples_length = len(samples)

        #             for query in page_obj:
        #                 try:
        #                     if query['material'] == 'soil' or  query['material'] == 'Soil':
        #                         js= JobSampleInfo.objects.get(job=job.id)
        #                         js.soil= samples_length
        #                         js.save()

        #                     elif query['material'] == 'plant' or query['material'] == 'Plant':
        #                         js= JobSampleInfo.objects.get(job=job.id)
        #                         js.plant= samples_length
        #                         js.save()

        #                     elif query['material'] == 'fertilizer' or query['material'] == 'Fertilizer':
        #                         js= JobSampleInfo.objects.get(job=job.id)
        #                         js.fertilizer= samples_length
        #                         js.save()

        #                     else:
        #                         js= JobSampleInfo.objects.get(job=job.id)
        #                         js.other= samples_length
        #                         js.other_description =  query['material']
        #                         js.save()

        #                 except Exception as e:
        #                     # print(str(e))
        #                     continue

        #         # if job.plant:
        #         #     for key, value in job.plant.items():
        #         #         if int(value) > 0:
        #         #             material_design.append("plant")
        #         # if job.soil:
        #         #     for key, value in job.soil.items():
        #         #         if int(value) > 0:
        #         #             material_design.append("soil")
        #         # if job.fertilizer:
        #         #     for key, value in job.fertilizer.items():
        #         #         if int(value) > 0:
        #         #             material_design.append("fertilizer")
        #         # if job.other:
        #         #     for key, value in job.other.items():
        #         #         if int(value) > 0:
        #         #             material_design.append("other")

        # for job in jobs:
        #     job_obj = Job.objects.get(id=job.id)
        #     # invoice=Invoice.objects.get(job=job_obj.id)

        #     # invoice.delete()

        #     create_invoice(job=job_obj)

        return Response("hey")


class gETtESTS1(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        invoice_items = InvoiceItem.objects.filter()

        jobs_2022 = Job.objects.filter(job_number__icontains="2022").order_by("-id")

        try:
            for job in jobs_2022:
                invoices = Invoice.objects.filter(job=job.id)

                for invoice in invoices:
                    invoice_items = InvoiceItem.objects.filter(invoice_id=invoice.id)

                    for invoice_item in invoice_items:
                        print(
                            invoice_item.description,
                            job.id,
                            invoice_item.id,
                            "=-------",
                        )
                        try:
                            if (
                                invoice_item.description
                                == "Mid Infrared Spectroscopy using the the Alpha Spectrometer for  soils/plants/manure/dry compost"
                            ):
                                desc = "Mid Infrared Spectroscopy using the Alpha Spectrometer for  soils/plants/manure/dry compost"
                            elif (
                                invoice_item.description
                                == "Laser Diffraction Paticle size Analysys-Soil Particle Size Distribution or Texture"
                            ):
                                desc = "ldpsa"
                            elif (
                                invoice_item.description
                                == "CN Analysis @ IsoAnalytical Lab UK"
                            ):
                                desc = "CN analysis at Iso-Analytical Laboratory in UK"
                            elif invoice_item.description == "Export Permit":
                                desc = "Export permit per package"
                            elif invoice_item.description == "Packaging":
                                desc = "Export permit per package"
                            elif (
                                invoice_item.description
                                == "Shipping to Isoanalytical UK"
                            ):
                                desc = "Courier charges to Iso-Analytical Laboratory UK per package"
                            elif (
                                invoice_item.description
                                == "Shipping to IsoAnalytical Lab UK"
                            ):
                                desc = "Courier charges to Iso-Analytical Laboratory UK per package"
                            elif (
                                invoice_item.description
                                == "CN Analysis @IsoAnalytical Lab UK"
                            ):
                                desc = "CN analysis at Iso-Analytical Laboratory in UK"
                            elif (
                                invoice_item.description
                                == "CN Analysis  @ IsoAnalitical Lab UK"
                            ):
                                desc = "CN analysis at Iso-Analytical Laboratory in UK"
                            elif (
                                invoice_item.description
                                == "CN Analysis @ Iso-Analytical Lab, UK"
                            ):
                                desc = "CN analysis at Iso-Analytical Laboratory in UK"
                            elif (
                                invoice_item.description == "Shipping to ISO-Analytical"
                            ):
                                desc = "Courier charges to Iso-Analytical Laboratory UK per package"
                            elif (
                                invoice_item.description == "Shipping to Iso-Anayitical"
                            ):
                                desc = "Courier charges to Iso-Analytical Laboratory UK per package"
                            else:
                                desc = invoice_item.description
                            unit_cost = UnitCost.objects.get(
                                Q(test__name=desc) & Q(from_date__icontains="2022")
                            )
                            invoice_item.test_id = unit_cost.id
                            invoice_item.save()
                        except UnitCost.DoesNotExist:
                            if (
                                invoice_item.description
                                == "Mid Infrared Spectroscopy using the the Alpha Spectrometer for  soils/plants/manure/dry compost"
                            ):
                                desc = "Mid Infrared Spectroscopy using the Alpha Spectrometer for  soils/plants/manure/dry compost"
                            elif (
                                invoice_item.description
                                == "CN Analysis @ IsoAnalytical Lab UK"
                            ):
                                desc = "CN analysis at Iso-Analytical Laboratory in UK"
                            elif invoice_item.description == "Export Permit":
                                desc = "Export permit per package"
                            elif invoice_item.description == "Packaging":
                                desc = "Export permit per package"
                            else:
                                desc = invoice_item.description
                            unit_cost = UnitCost.objects.get(
                                Q(test__description=desc)
                                & Q(from_date__icontains="2022")
                            )
                            invoice_item.test_id = unit_cost.id
                            invoice_item.save()

            return Response("hey")

        except Exception as e:
            print(str(e), "--------------")
            return Response(
                {
                    "mm": str(e),
                }
            )


class ReportsAPIView(GenericAPIView):
    permission_classes = [AllowAny]
    template_name = "reports.html"

    def get(self, request):
        reports = Report.objects.all()

        report_data = ReportSerializer(reports, many=True).data
        return Response(report_data)


class MoveReportsAPIView(GenericAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        documentations = ProjectDocumentationUpload.objects.all()

        for documentation in documentations:
            try:
                if documentation.category.id == 1:
                    documentation.report = Report.objects.get(id=6)
                    documentation.save()
            except:
                continue

        for documentation in documentations:
            try:
                if documentation.category.id == 2:
                    documentation.report = Report.objects.get(id=3)
                    documentation.save()
            except:
                continue

        jobs_reports = ReportModel.objects.all()
        for reports in jobs_reports:
            ProjectDocumentationUpload.objects.create(
                report=reports.report,
                job=reports.job_id,
                uploaded_by=reports.uploaded_by,
            )

        return Response("")


class DownloadRawOpusFiles(GenericAPIView):
    def get(self, request):
        job_id = request.GET.get("job_id", None)
        instrument_id = request.GET.get("instrument_id", None)

        instrument = LabInstrument.objects.get(id=instrument_id)

        # Define the directory path containing the files to be zipped
        directory_part = str(job_id)  # Ensure the directory part is a string

        # Try both potential paths
        paths_to_try = [
            os.path.join(
                settings.MEDIA_ROOT, "jobs/updated_opus_files/", f"{directory_part}.zip"
            ),
            os.path.join(settings.MEDIA_ROOT, "jobs/zip/", f"{directory_part}.zip"),
        ]

        for data_path in paths_to_try:
            if os.path.exists(data_path):
                # File found, prepare for download
                file_name = f"job_{job_id}_opus_files.zip"

                response = FileResponse(open(data_path, "rb"))
                response["Content-Type"] = "application/zip"
                response["Content-Disposition"] = f'attachment; filename="{file_name}"'
                return response

        # If we've tried all paths and found nothing
        return HttpResponseNotFound("Requested file not found")


class DeleteTestsAPIView(GenericAPIView):
    def get(self, request, job_number):
        url = reverse("consolidated-instruments-data")

        if request.user.email == "s.nyagaka@cifor.icraf":
            job = Job.objects.get(job_number=job_number)

            job_test_id = request.GET.get("job_test_id", None)

            job_test = JobTest.objects.filter(job=job.id).filter(id=job_test_id)
            job_test.delete()

            return redirect(url)
        return redirect(url)


class GenerateInvoice(GenericAPIView):
    def get(self, request):
        pass


class UpdateSSNView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            sn = Sample.objects.order_by("-job_id").first()
            
            

            start_ssn = "WA083027"
            end_ssn = "WA084817"
            new_start_ssn = "WA079994"
            new_end_ssn = "WA081784"

            last_sample_temp = (
                Sample.objects.filter(version_one=False).filter(job_id=817).last()
            )


            samples = Sample.objects.filter(job_id=818)

            # count = 0

            # for sample in samples:
            #     
            #     
            #     count += 1
            #     new_ssn = 79993 + count
            #     print(new_ssn)
            #     sample.number  = "WA0{}".format(new_ssn)
            #     sample.save()

            return Response(
                {"message": "SSNs updated successfully"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# class OpusFileWriter(APIView):
#     permission_classes = [AllowAny]

#     def get(self, request):
#         # Example usage
#         data = {
#             "SSN": "0000273",
#             "Material": "soil",
#             "Lab": "srl",
#             "Instrument": "Alpha II",
#             "Scan_date": "09/07/2024",
#             "Time": "11:59:53.390 ",
#             "Zone": "GMT-7",
#             "Duration": "28.700000047683716",
#             "Operator": Regional Admin,
#             "Resolution": "8.0",
#             "Zero_filling_Factor": "4",
#             "Number_points": "1705",
#             "Laser_Wavenumber": "11675.69119835",
#             "Wavenumber_one": "3995.9597044665443",
#             "Wavenumber_last": "498.7253252107705",
#             "Min_absorbance": "1.3491865396499634",
#             "Max_Absorbance": "2.401015520095825",
#             "3996.0": None,
#             "3993.9": 1.349934584228649,
#             "3991.9": 1.3505905578829382,
#             "3989.8": 1.3511324922965717
#         }

#         output_directory = os.path.join(settings.BASE_DIR, 'opus_files')
#         filepath = self.write_opus_file(data, output_directory)
#         return Response({"message": "OPUS file created", "filepath": filepath})

#     def write_opus_file(self, data, output_directory):
#         # Extract SSN from the data
#         ssn = data.get('SSN', 'unknown')

#         # Create the output directory if it doesn't exist
#         os.makedirs(output_directory, exist_ok=True)

#         # Create the filename
#         filename = f"{ssn}.opus"
#         filepath = os.path.join(output_directory, filename)

#         # Write the data to the OPUS file
#         with open(filepath, 'w') as f:
#             # Write metadata
#             for key, value in data.items():
#                 if key not in ['SSN'] and not isinstance(value, (dict, list)):
#                     f.write(f"{key}={value}\n")

#             # Write spectral data
#             f.write("SpectralData\n")
#             for wavenumber, absorbance in data.items():
#                 if isinstance(wavenumber, (float, int)) and absorbance is not None:
#                     f.write(f"{wavenumber},{absorbance}\n")
#             f.write("EndSpectralData\n")

#         return filepath


User = get_user_model()


class OpusFileWriter(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    
    def check_and_notify_instrument_service(self, request):
        today = timezone.now().date()
        
        # Get the admin groups
        admin_groups = Group.objects.filter(name__in=["Regional Admin", "Regional Admin"])

        # Fetch instruments that need servicing
        instruments_needing_service = LabInstrument.objects.filter(
            is_active=True,
            is_serviced=True
        ).select_related('organization', 'lab')

        # Filter instruments based on service schedule
        instruments_due = [
            instrument for instrument in instruments_needing_service
            if instrument.last_serviced and 
            (today - instrument.last_serviced).days >= instrument.often_serviced
        ]

        # Group instruments by organization
        instruments_by_org = {}
        for instrument in instruments_due:
            if instrument.organization not in instruments_by_org:
                instruments_by_org[instrument.organization] = []
            instruments_by_org[instrument.organization].append(instrument)

        # Prepare bulk emails
        emails = []
        email_results = []

        for organization, instruments in instruments_by_org.items():
            print(f"Processing organization: {organization.name}")

            # Fetch all active users for this organization
            org_users = User.objects.filter(organization=organization, is_active=True)

            # Filter admin users
            admin_users = [
                user for user in org_users
                if any(group in user.groups.all() for group in admin_groups)
            ]

            subject = f"Instruments Due for Servicing - {organization.name}"
            message = f"The following instruments for {organization.name} in { pycountry.countries.get(alpha_2=organization.country).name} are due for servicing:\n\n"

            for instrument in instruments:
                instrument_detail_url = reverse("lab-instrument-list")
                full_instrument_detail_url = f"{settings.BASE_URL}{instrument_detail_url}"
                days_since_service = (today - instrument.last_serviced).days if instrument.last_serviced else "N/A"
                message += f"Instrument: {instrument.name}\n"
                message += f"Lab: {instrument.lab.name if instrument.lab else 'N/A'}\n"
                message += f"Last Serviced: {instrument.last_serviced or 'Never'}\n"
                message += f"Days Since Last Service: {days_since_service}\n"
                message += f"Service Frequency (days): {instrument.often_serviced}\n"
                message += f"Instrument Detail Link: {full_instrument_detail_url}\n\n"

            recipient_list = [user.email for user in admin_users]

            if recipient_list:
                emails.append((
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    # recipient_list
                    ['salmanyagaka@gmail.com']
                ))

            email_results.append({
                "organization": organization.name,
                "admin_count": len(admin_users),
                "instrument_count": len(instruments),
            })

        # Send emails in bulk
        try:
            send_mass_mail(emails, fail_silently=False)
            email_status = "Success"
        except Exception as e:
            email_status = f"Error: {str(e)}"

        # Print query statistics
        print(f"Number of queries: {len(connection.queries)}")

        return Response( {
            "message": f"Processed {len(instruments_due)} instruments due for servicing across {len(instruments_by_org)} organizations.",
            "email_results": email_results,
            "email_status": email_status,
        })

    def unauthorized(self, request):
        two_days_ago = timezone.now() - timezone.timedelta(days=2)

        # Get the admin group
        admin_group = Group.objects.get(name="Regional Admin")

        # Fetch unauthorized jobs and related organizations
        unauthorized_jobs = Job.objects.filter(
            testing_authorized_by__isnull=True, created_at__lte=two_days_ago
        ).select_related("organization")

        # Group jobs by organization
        jobs_by_org = {}
        for job in unauthorized_jobs:
            if job.organization not in jobs_by_org:
                jobs_by_org[job.organization] = []
            jobs_by_org[job.organization].append(job)

        # Prepare bulk emails
        emails = []
        email_results = []

        for organization, jobs in jobs_by_org.items():
            # Fetch admin users for this organization
            admin_users = User.objects.filter(
                groups=admin_group, organization=organization
            ).select_related("organization")

            subject = f"Unauthorized Jobs for {organization.name}"
            message = f"The following jobs for {organization.name} have been unauthorized for more than 2 days:\n\n"

            for job in jobs:
                job_detail_url = request.build_absolute_uri(
                    reverse("job-detail", args=[job.pk])
                )
                formatted_date = job.created_at.strftime("%Y-%m-%d %H:%M:%S")
                message += (
                    f"Job Number: {job.job_number}, Created at: {formatted_date}\n"
                )
                message += f"Job Detail Link: {job_detail_url}\n\n"

            recipient_list = [user.email for user in admin_users]

            if recipient_list:
                emails.append(
                    (
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        ["salmanyagaka@gmail.com"],
                    )
                )

            email_results.append(
                {
                    "organization": organization.name,
                    "admin_count": len(admin_users),
                    "job_count": len(jobs),
                }
            )

        # Send emails in bulk
        try:
            send_mass_mail(emails, fail_silently=False)
            email_status = "Success"
        except Exception as e:
            email_status = f"Error: {str(e)}"

        # Print query statistics
        print(f"Number of queries: {len(connection.queries)}")

        return Response(
            {
                "message": f"Processed {len(unauthorized_jobs)} unauthorized jobs for {len(jobs_by_org)} organizations.",
                "email_results": email_results,
                "email_status": email_status,
            }
        )
        # return Response(messages)

    def check_test_schedule_overdue(self, request):
        today = timezone.now().date()

        # Get the admin group
        admin_group = Group.objects.get(name="Regional Admin")

        # Fetch overdue jobs
        overdue_jobs = JobTest.objects.filter(
            start_date__lt=today, job__completion_status=1
        ).select_related("job", "assignee", "job__organization")

        # Group jobs by organization
        jobs_by_org = {}
        for job_test in overdue_jobs:
            if job_test.job.organization not in jobs_by_org:
                jobs_by_org[job_test.job.organization] = []
            jobs_by_org[job_test.job.organization].append(job_test)

        # Prepare bulk emails
        emails = []
        email_results = []

        for organization, job_tests in jobs_by_org.items():
            # Fetch admin users for this organization
            admin_users = User.objects.filter(
                groups=admin_group, organization=organization
            )

            subject = f"Overdue Jobs for {organization.name}"
            message = f"The following jobs for {organization.name} are overdue:\n\n"

            for job_test in job_tests:
                job_detail_url = reverse("job-detail", args=[job_test.job.pk])
                full_job_detail_url = f"{settings.BASE_DIR}{job_detail_url}"

                # full_job_detail_url = request.build_absolute_uri(reverse('job-detail', args=[job_test.job.pk]))

                formatted_date = job_test.start_date.strftime("%Y-%m-%d")
                message += f"Job Number: {job_test.job.job_number}\n"
                message += f"Scheduled Start: {formatted_date}\n"
                message += f"Test: {job_test.test.test.name}\n"
                message += f"Assignee: {job_test.assignee.email if job_test.assignee else 'Not Assigned'}\n"
                message += f"Job Detail Link: {full_job_detail_url}\n\n"

            # Send to admin users
            admin_recipient_list = [user.email for user in admin_users]
            if admin_recipient_list:
                # emails.append((subject, message, settings.DEFAULT_FROM_EMAIL, admin_recipient_list))
                emails.append(
                    (
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        ["salmanyagaka@gmail.com"],
                    )
                )

            # Send to assignees
            for job_test in job_tests:
                if job_test.assignee:
                    assignee_subject = f"Overdue Job: {job_test.job.job_number}"
                    assignee_message = (
                        f"The following job assigned to you is overdue:\n\n"
                    )
                    assignee_message += f"Job Number: {job_test.job.job_number}\n"
                    assignee_message += f"Scheduled Start: {formatted_date}\n"
                    assignee_message += f"Test: {job_test.test.test.name}\n"
                    assignee_message += f"Job Detail Link: {full_job_detail_url}\n\n"
                    # emails.append((assignee_subject, assignee_message, settings.DEFAULT_FROM_EMAIL, [job_test.assignee.email]))
                    emails.append(
                        (
                            assignee_subject,
                            assignee_message,
                            settings.DEFAULT_FROM_EMAIL,
                            ["salmanyagaka@gmail.com"],
                        )
                    )

            email_results.append(
                {
                    "organization": organization.name,
                    "admin_count": len(admin_users),
                    "job_count": len(job_tests),
                }
            )

        # Send emails in bulk
        try:
            send_mass_mail(emails, fail_silently=False)
            email_status = "Success"
        except Exception as e:
            email_status = f"Error: {str(e)}"

        # Print query statistics
        print(f"Number of queries: {len(connection.queries)}")

        return Response(
            {
                "message": f"Processed {len(overdue_jobs)} overdue jobs for {len(jobs_by_org)} organizations.",
                "email_results": email_results,
                "email_status": email_status,
            }
        )

    def check_and_notify_overdue_project_documentation(self, request):
        today = timezone.now().date()

        # Get the admin group
        admin_groups = Group.objects.filter(name__in=["Regional Admin", "Regional Admin"])

        # Fetch overdue project documentation uploads
        overdue_docs = ProjectDocumentationUpload.objects.filter(
            start_date__lt=today, completion_status=1, is_uploaded=False
        ).select_related("job", "assignee", "job__organization", "category")

        # Group documents by organization
        docs_by_org = {}
        for doc in overdue_docs:
            if doc.job.organization not in docs_by_org:
                docs_by_org[doc.job.organization] = []
            docs_by_org[doc.job.organization].append(doc)

        # Prepare bulk emails
        emails = []
        email_results = []

        for organization, docs in docs_by_org.items():
            # Fetch all active users for this organization
            org_users = User.objects.filter(organization=organization, is_active=True)
            # print(f"Number of active users in organization: {org_users.count()}")

            # Filter admin users
            admin_users = [
                user
                for user in org_users
                if any(group in user.groups.all() for group in admin_groups)
            ]

            # print(f"Number of admin users found: {len(admin_users)}")
            # for user in admin_users:
            #     print(f"Admin user: {user.email}, Groups: {[g.name for g in user.groups.all()]}")

            subject = f"Overdue Project Documentation for {organization.name}"
            message = f"The following project documentation for {organization.name} is overdue:\n\n"

            for doc in docs:
                # job_detail_url = reverse('job-detail', args=[doc.job.pk])
                # full_job_detail_url = f"{settings.SITE_URL}{job_detail_url}"
                query_params = urlencode({"job_number": doc.job.job_number})

                report_detail_url = reverse("view-project-documentation")
                # full_report_detail_url = f"{settings.BASE_URL}{report_detail_url}?{query_params}"
                full_report_detail_url = (
                    f"{settings.BASE_URL}/view-documentation/?{query_params}"
                )
                formatted_date = doc.start_date.strftime("%Y-%m-%d")
                message += f"Job Number: {doc.job.job_number}\n"
                message += f"Project Title: {doc.project_title}\n"
                message += (
                    f"Category: {doc.report.name if doc.report else 'Not Specified'}\n"
                )
                message += f"Scheduled Start: {formatted_date}\n"
                message += f"Assignee: {doc.assignee.email if doc.assignee else 'Not Assigned'}\n"
                message += f"Job Detail Link: {full_report_detail_url}\n\n"

            # Send to admin users
            admin_recipient_list = [user.email for user in admin_users]
            if admin_recipient_list:
                # emails.append((subject, message, settings.DEFAULT_FROM_EMAIL, admin_recipient_list))
                emails.append(
                    (
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        ["salmanyagaka@gmail.com"],
                    )
                )

            # Send to assignees
            for doc in docs:
                if doc.assignee:
                    assignee_subject = (
                        f"Overdue Project Documentation: {doc.job.job_number}"
                    )
                    assignee_message = f"The following project documentation assigned to you is overdue:\n\n"
                    assignee_message += f"Job Number: {doc.job.job_number}\n"
                    assignee_message += f"Project Title: {doc.project_title}\n"
                    assignee_message += f"Category: {doc.category.name if doc.category else 'Not Specified'}\n"
                    assignee_message += f"Scheduled Start: {formatted_date}\n"
                    assignee_message += f"Job Detail Link: {full_report_detail_url}\n\n"
                    # emails.append((assignee_subject, assignee_message, settings.DEFAULT_FROM_EMAIL, [doc.assignee.email]))
                    emails.append(
                        (
                            assignee_subject,
                            assignee_message,
                            settings.DEFAULT_FROM_EMAIL,
                            ["salmanyagaka@gmail.com"],
                        )
                    )

            email_results.append(
                {
                    "organization": organization.name,
                    "admin_count": len(admin_users),
                    "doc_count": len(docs),
                }
            )

        # Send emails in bulk
        try:
            send_mass_mail(emails, fail_silently=False)
            email_status = "Success"
        except Exception as e:
            email_status = f"Error: {str(e)}"

        # Print query statistics
        print(f"Number of queries: {len(connection.queries)}")

        return Response(
            {
                "message": f"Processed {len(overdue_docs)} overdue project documentation for {len(docs_by_org)} organizations.",
                "email_results": email_results,
                "email_status": email_status,
            }
        )

    def check_and_notify_overdue_invoices(self, request):
        today = timezone.now().date()

        # Get the admin group
        admin_groups = Group.objects.filter(
            name__in=[
                "Regional Admin",
                "Lab Invoice Editor",
                "Lab Invoicing viewer",
                "Lab invoices information  entry",
            ]
        )

        # Fetch overdue invoices
        overdue_invoices = Invoice.objects.filter(
            due_date__lt=today, due_date__isnull=False, is_paid=False
        ).select_related("job", "job__organization")

        # Group invoices by organization
        invoices_by_org = {}
        for invoice in overdue_invoices:
            if invoice.job.organization not in invoices_by_org:
                invoices_by_org[invoice.job.organization] = []
            invoices_by_org[invoice.job.organization].append(invoice)

        # Prepare bulk emails
        emails = []
        email_results = []

        # Base URL for development. In production, you should use a configuration variable.

        for organization, invoices in invoices_by_org.items():
            # Fetch admin users for this organization
            org_users = User.objects.filter(organization=organization, is_active=True)
            admin_users = [
                user
                for user in org_users
                if any(group in user.groups.all() for group in admin_groups)
            ]

            subject = f"Overdue Invoices for {organization.name}"
            message = f"The following invoices for {organization.name} are overdue:\n\n"

            for invoice in invoices:
                # Construct the URL for the invoice detail
                invoice_detail_url = f"{settings.BASE_URL}/invoices/{invoice.pk}"

                formatted_due_date = invoice.due_date.strftime("%Y-%m-%d")
                message += f"Invoice Number: {invoice.number}\n"
                message += f"Job Number: {invoice.job.job_number}\n"
                message += f"Due Date: {formatted_due_date}\n"
                message += f"Total Amount: ${invoice.total_amount}\n"
                message += f"Balance Due: ${invoice.balance}\n"
                message += f"Invoice Detail Link: {invoice_detail_url}\n\n"

            # Send to admin users
            admin_recipient_list = [user.email for user in admin_users]
            if admin_recipient_list:
                # emails.append((subject, message, settings.DEFAULT_FROM_EMAIL, admin_recipient_list))
                emails.append(
                    (
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        ["salmanyagaka@gmail.com"],
                    )
                )

            email_results.append(
                {
                    "organization": organization.name,
                    "admin_count": len(admin_users),
                    "invoice_count": len(invoices),
                }
            )

        # Send emails in bulk
        try:
            send_mass_mail(emails, fail_silently=False)
            email_status = "Success"
        except Exception as e:
            email_status = f"Error: {str(e)}"

        # Print query statistics
        print(f"Number of queries: {len(connection.queries)}")

        return Response(
            {
                "message": f"Processed {len(overdue_invoices)} overdue invoices for {len(invoices_by_org)} organizations.",
                "email_results": email_results,
                "email_status": email_status,
            }
        )

        #     def get(self, request):
        #         # Example usage
        #         data = {
        #             "SSN": "0000273",
        #             "Material": "soil",
        #             "Lab": "srl",
        #             "Instrument": "Alpha II",
        #             "Scan_date": "09/07/2024",
        #             "Time": "11:59:53.390",
        #             "Zone": "GMT-7",
        #             "Duration": 28.700000047683716,
        #             "Operator": Regional Admin,
        #             "Resolution": 8.0,
        #             "Zero_filling_Factor": 4,
        #             "Number_points": 1705,
        #             "Laser_Wavenumber": 11675.69119835,
        #             "Wavenumber_one": 3995.9597044665443,
        #             "Wavenumber_last": 498.7253252107705,
        #             "Min_absorbance": 1.3491865396499634,
        #             "Max_Absorbance": 2.401015520095825,
        #             "Spectral_data": {
        #                 3996.0: None,
        #                 3993.9: 1.349934584228649,
        #                 3991.9: 1.3505905578829382,
        #                 3989.8: 1.3511324922965717
        #                 # ... (other spectral data points)
        #             }
        #         }

        #         output_directory = os.path.join(settings.BASE_DIR, 'media', 'jobs', 'updated_opus_files')
        #         filepath = self.write_opus_file(data, output_directory)
        #         return Response({"message": "OPUS file created", "filepath": filepath})

        #     CORE_FIELDS_OPUS_CONVERSION = [
        #     "SSN", "Lab", "Material", "Instrument", "Scan_date", "Time", "Zone", "Duration",
        #     "Operator", "Resolution", "Zero_filling_Factor", "Number_points", "Laser_Wavenumber",
        #     "Wavenumber_one", "Wavenumber_last", "Min_absorbance", "Max_Absorbance",
        # ]
        #     def create_opus_header(self):
        #         # This is a simplified OPUS header. You may need to adjust this based on the actual OPUS file format.
        #         header = bytearray()
        #         header.extend(b'OPUS')  # File identifier
        #         header.extend(struct.pack('>I', 1))  # Version number
        #         header.extend(struct.pack('>I', 0))  # File size (placeholder)
        #         header.extend(struct.pack('>I', 0))  # Number of blocks (placeholder)
        #         return header

        #     def write_opus_file(self, data, output_directory):
        # Extract SSN from the data
        ssn = data.get("SSN", "unknown")

        # Create the output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)

        # Create the filename with .0 extension
        filename = f"{ssn}.0"
        filepath = os.path.join(output_directory, filename)

        # Write the data to the binary OPUS file
        with open(filepath, "wb") as f:
            # Write a simple header (this is a placeholder, not a real OPUS header)
            # f.write(b'OPUS\x00\x01')
            f.write(self.create_opus_header())
            # Write metadata
            for key, value in data.items():
                if key not in ["SSN", "Spectral_data"]:
                    key_bytes = key.encode("ascii")
                    if isinstance(value, str):
                        value_bytes = value.encode("ascii")
                        f.write(struct.pack(">H", len(key_bytes)))
                        f.write(key_bytes)
                        f.write(struct.pack(">H", len(value_bytes)))
                        f.write(value_bytes)
                    elif isinstance(value, (int, float)):
                        f.write(struct.pack(">H", len(key_bytes)))
                        f.write(key_bytes)
                        f.write(struct.pack(">d", float(value)))

            # Write spectral data
            f.write(b"SPEC")
            spectral_data = {
                float(k): v
                for k, v in data.items()
                if isinstance(k, (float, int)) and k not in CORE_FIELDS_OPUS_CONVERSION
            }

            # spectral_data = data.get('Spectral_data', {})
            f.write(struct.pack(">I", len(spectral_data)))
            for wavenumber, absorbance in spectral_data.items():
                if absorbance is not None:
                    f.write(struct.pack(">ff", float(wavenumber), float(absorbance)))

        return filepath
    


class ProcessSampleDataAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # 1. Access the SampleData table with records that have instrument == 'Alpha II'
        jobs = SampleData.objects.filter(instrument='Alpha II').annotate(
            job_id=F('ssn__job__id'),
            job_number=F('ssn__job__job_number')
        ).values('job_id', 'job_number').distinct()

        job_dict = {job['job_id']: job['job_number'] for job in jobs}

        base_dir = os.path.join(settings.BASE_DIR, "media", "jobs", "zip")
        temp_dir = os.path.join(settings.BASE_DIR, "media", "temp", "AlphaII")
        os.makedirs(temp_dir, exist_ok=True)

        processed_jobs = []
        errors = []

        # Create a new zip file to contain all job zip files
        master_zip_path = os.path.join(temp_dir, "AlphaII_all_jobs.zip")
        with zipfile.ZipFile(master_zip_path, 'w') as master_zip:
            for job_id, job_number in job_dict.items():
                source_dir = os.path.join(base_dir, f"{job_id}")

                if os.path.exists(source_dir) and os.path.isdir(source_dir):
                    files = os.listdir(source_dir)
                    zip_files = [f for f in files if f.endswith('.zip')]

                    if zip_files:
                        zip_file_name = zip_files[0]
                        zip_file_path = os.path.join(source_dir, zip_file_name)

                        # Add the job zip file to the master zip
                        master_zip.write(zip_file_path, f"{job_number}/{zip_file_name}")

                        processed_jobs.append({
                            "job_id": job_id,
                            "job_number": job_number,
                            "file_name": zip_file_name
                        })
                    else:
                        errors.append(f"No zip file found for job_id: {job_id}, job_number: {job_number}")
                else:
                    errors.append(f"Directory not found for job_id: {job_id}, job_number: {job_number}")

        response_data = {
            "message": f"Processing completed. Processed {len(processed_jobs)} unique job(s).",
            "processed_jobs": processed_jobs,
            "errors": errors
        }

        # Return the master zip file as a FileResponse
        if os.path.exists(master_zip_path):
            response = FileResponse(open(master_zip_path, 'rb'), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="AlphaII_all_jobs.zip"'
            return response
        else:
            return Response({"error": "Failed to create the master zip file"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)  



# class ProcessSampleDataAPIView(APIView):
#     permission_classes = [AllowAny]
#     def post(self, request):
#         # 1. Access the SampleData table with records that have instrument == 'Alpha II'
#         # Get job_id and job_number, ensuring uniqueness
#         jobs = SampleData.objects.filter(instrument='Alpha II').annotate(
#             job_id=F('ssn__job__id'),
#             job_number=F('ssn__job__job_number')
#         ).values('job_id', 'job_number').distinct()

#         # Convert to a dictionary for easy lookup
#         job_dict = {job['job_id']: job['job_number'] for job in jobs}

#         # Define the base directory for zip files
#         base_dir = os.path.join(
#             settings.BASE_DIR,
#             "media",
#             "jobs",
#             "zip"
#         )

#         # Define the destination directory in Documents
#         dest_dir = os.path.expanduser("~/Documents/AlphaII/")

#         # Create the destination directory if it doesn't exist
#         os.makedirs(dest_dir, exist_ok=True)

#         processed_jobs = []
#         errors = []

#         for job_id, job_number in job_dict.items():
#             # 2. Construct the source directory for this job
#             source_dir = os.path.join(base_dir, f"{job_id}")

#             # Check if the directory exists
#             if os.path.exists(source_dir) and os.path.isdir(source_dir):
#                 # Get all files in the directory
#                 files = os.listdir(source_dir)
#                 zip_files = [f for f in files if f.endswith('.zip')]

#                 if zip_files:
#                     # Assume the first zip file is the one we want
#                     zip_file_name = zip_files[0]
#                     zip_file_path = os.path.join(source_dir, zip_file_name)

#                     # Create a new directory for this job in the destination, using job_number
#                     job_dest_dir = os.path.join(dest_dir, f"job_{job_number}")
#                     os.makedirs(job_dest_dir, exist_ok=True)

#                     # 3. Copy the file to the job-specific directory
#                     dest_file_path = os.path.join(job_dest_dir, zip_file_name)
#                     shutil.copy2(zip_file_path, dest_file_path)
#                     processed_jobs.append({
#                         "job_id": job_id,
#                         "job_number": job_number,
#                         "file_name": zip_file_name,
#                         "destination": job_dest_dir
#                     })
#                 else:
#                     errors.append(f"No zip file found for job_id: {job_id}, job_number: {job_number}")
#             else:
#                 errors.append(f"Directory not found for job_id: {job_id}, job_number: {job_number}")

#         response_data = {
#             "message": f"Processing completed. Processed {len(processed_jobs)} unique job(s).",
#             "processed_jobs": processed_jobs,
#             "errors": errors
#         }

#         return Response(response_data, status=status.HTTP_200_OK)




_opus_bundle_logger = logging.getLogger("jobs.opus_bundle")

MAX_JOBS_PER_REQUEST = 200


class OpusBundleDownloadThrottle(SimpleRateThrottle):
    scope = "opus_bundle_download"

    def get_cache_key(self, request, view):
        ident = request.user.pk if request.user and request.user.is_authenticated else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class DownloadTokenAuthentication(BaseAuthentication):
    """
    Accepts a token via:
      - Query param:  ?token=<uuid>  (note: token appears in server logs; prefer the header)
      - Header:       Authorization: Token <uuid>
    """

    def authenticate(self, request):

        raw = (
            request.GET.get("token")
            or self._from_header(request)
        )
        if not raw:
            return None

        try:
            import uuid
            dt = DownloadToken.objects.select_related("created_by").get(
                token=uuid.UUID(str(raw))
            )
        except (DownloadToken.DoesNotExist, ValueError):
            raise AuthenticationFailed("Invalid download token.")

        if not dt.is_valid():
            raise AuthenticationFailed("Download token is inactive or expired.")

        return (dt.created_by, dt)

    def _from_header(self, request):
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "token":
            return parts[1]
        return None


class DownloadTokenManageView(APIView):
    """
    POST  /jobs/download-tokens          — create a new token (JWT auth required)
    GET   /jobs/download-tokens          — list your tokens
    DELETE /jobs/download-tokens?token=  — revoke a token
    """

    def get(self, request):
        from .models import DownloadToken
        tokens = DownloadToken.objects.filter(created_by=request.user).values(
            "token", "label", "expires_at", "is_active", "created_at"
        )
        return Response(list(tokens))

    def post(self, request):
      

        label = request.data.get("label", "")
        expires_at_raw = request.data.get("expires_at")
        expires_at = None
        if expires_at_raw:
            try:
                expires_at = dateutil.parser.parse(expires_at_raw)
                if timezone.is_naive(expires_at):
                    expires_at = timezone.make_aware(expires_at)
            except Exception:
                return Response(
                    {"error": "Invalid expires_at format. Use ISO 8601."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        dt = DownloadToken.objects.create(
            created_by=request.user, label=label, expires_at=expires_at
        )
        return Response(
            {
                "token": str(dt.token),
                "label": dt.label,
                "expires_at": dt.expires_at,
                "created_at": dt.created_at,
            },
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        from .models import DownloadToken
        import uuid

        raw = request.GET.get("token")
        if not raw:
            return Response({"error": "token param required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            DownloadToken.objects.filter(
                created_by=request.user, token=uuid.UUID(raw)
            ).update(is_active=False)
        except ValueError:
            return Response({"error": "Invalid token format."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Token revoked."})


class DownloadOpusBundleView(APIView):
    authentication_classes = [DownloadTokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [OpusBundleDownloadThrottle]
    """
    GET /jobs/download-opus-bundle

    Query params (at least one filter required):
        country                 (optional) — one or more country names, comma-separated e.g. "Kenya,Uganda"
        samples_collected_from  (optional, YYYY-MM-DD) — filters by samples_received_on
        samples_collected_to    (optional, YYYY-MM-DD) — filters by samples_received_on
        include_wetchem         (optional, "true"/"false") — include wet-chem xlsx

    Returned zip structure:
        {job_number}_{site}_{date_range}.zip
        └── {job_number}_{site}/
            ├── opus_files.zip
            ├── {job_number}_{site}_wetchem.xlsx        (if include_wetchem=true)
            └── {job_number}_{site}_login_sheet.xlsx    (if include_login_sheet=true)
    """

    def get(self, request):
        country_param = request.GET.get("country", "").strip()
        site_param = request.GET.get("site_name", "").strip()
        date_from = request.GET.get("samples_uploaded_from_date", "").strip()
        date_to = request.GET.get("samples_uploaded_to_date", "").strip()
        include_wetchem = request.GET.get("include_wetchem", "false").lower() == "true"

        if not date_from or not date_to:
            return Response(
                {"error": "samples_uploaded_from_date and samples_uploaded_to_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            d_from = dt.date.fromisoformat(date_from)
            d_to = dt.date.fromisoformat(date_to)
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if d_to < d_from:
            return Response(
                {"error": "samples_uploaded_to_date must be after samples_uploaded_from_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        delta_months = (d_to.year - d_from.year) * 12 + (d_to.month - d_from.month)
        if delta_months > 6 or (delta_months == 6 and d_to.day > d_from.day):
            return Response(
                {"error": "Date range cannot exceed 6 months."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            jobs_qs = Job.objects.select_related("organization")

            if site_param:
                site_names = [s.strip() for s in site_param.split(",") if s.strip()]
                from django.db.models import Q
                site_filter = Q()
                for s in site_names:
                    site_filter |= Q(site__icontains=s)
                jobs_qs = jobs_qs.filter(site_filter)

            if country_param:
                country_codes = []
                for raw_country in [c.strip() for c in country_param.split(",") if c.strip()]:
                    match = None
                    try:
                        match = pycountry.countries.get(name=raw_country)
                        if not match:
                            match = pycountry.countries.search_fuzzy(raw_country)[0]
                    except LookupError:
                        pass
                    if not match:
                        return Response(
                            {"error": f"Country not found: {raw_country}. Please check the spelling and try again."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    country_codes.append(match.alpha_2)
                jobs_qs = jobs_qs.filter(country__in=country_codes)

            if date_from:
                jobs_qs = jobs_qs.filter(samples_uploaded_at__date__gte=date_from)
            if date_to:
                jobs_qs = jobs_qs.filter(samples_uploaded_at__date__lte=date_to)

            jobs = list(jobs_qs)
            if not jobs:
                return Response(
                    {"error": "No jobs found matching the given filters."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if len(jobs) > MAX_JOBS_PER_REQUEST:
                return Response(
                    {
                        "error": f"Query matches {len(jobs)} jobs, which exceeds the limit of {MAX_JOBS_PER_REQUEST}. "
                                 "Please narrow your date range or add a country/site filter."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            MAX_BUNDLE_BYTES = 1.5 * 1024 ** 3
            estimated_size = 0
            for job in jobs:
                for candidate in [
                    os.path.join(settings.MEDIA_ROOT, "jobs/zip/", str(job.pk), f"{job.pk}.zip"),
                    os.path.join(settings.MEDIA_ROOT, "jobs/zip/", str(job.pk), f"job_{job.pk}_opus_files.zip"),
                ]:
                    if os.path.exists(candidate):
                        estimated_size += os.path.getsize(candidate)
                        break
            if estimated_size > MAX_BUNDLE_BYTES:
                size_gb = estimated_size / 1024 ** 3
                return Response(
                    {
                        "error": f"Estimated bundle size ({size_gb:.2f} GB) exceeds the 1.5 GB limit. "
                                 "Please reduce the date range or add a country/site filter."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            date_parts = [p for p in [date_from, date_to] if p]
            date_suffix = ("_" + "_to_".join(date_parts)) if date_parts else ""
            country_label = re.sub(r"[^\w\-]", "_", country_param or "all").strip("_")
            outer_zip_name = f"{country_label}{date_suffix}.zip"

            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
            try:
                files_added = 0
                with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as outer_zip:
                    for job in jobs:
                        job_id = job.pk
                        job_number = job.job_number
                        site_safe = re.sub(r"[^\w\-]", "_", job.site or "unknown").strip("_")
                        inner_folder = f"{job_number}_{site_safe}"

                        opus_zip_candidates = [
                            os.path.join(settings.MEDIA_ROOT, "jobs/zip/", str(job_id), f"{job_id}.zip"),
                            os.path.join(settings.MEDIA_ROOT, "jobs/zip/", str(job_id), f"job_{job_id}_opus_files.zip"),
                        ]
                        opus_zip_path = next((p for p in opus_zip_candidates if os.path.exists(p)), None)

                        if opus_zip_path:
                            outer_zip.write(opus_zip_path, f"{inner_folder}/opus_files.zip")
                        files_added += 1

                        outer_zip.writestr(
                            f"{inner_folder}/{job_number}_{site_safe}_login_sheet.xlsx",
                            self._build_login_sheet_xlsx(job),
                        )

                        outer_zip.writestr(
                            f"{inner_folder}/{job_number}_{site_safe}_flat_table.xlsx",
                            self._build_sample_data_xlsx(job, has_opus=bool(opus_zip_path)),
                        )

                        if include_wetchem:
                            outer_zip.writestr(
                                f"{inner_folder}/{job_number}_{site_safe}_wetchem.xlsx",
                                self._build_wetchem_xlsx(job),
                            )

                zip_size = tmp.tell()
                tmp.seek(0)

                def file_iterator(f, path, chunk_size=8192):
                    try:
                        for chunk in FileWrapper(f, chunk_size):
                            yield chunk
                    finally:
                        f.close()
                        os.unlink(path)

                response = StreamingHttpResponse(
                    file_iterator(tmp, tmp.name), content_type="application/zip"
                )
                response["Content-Disposition"] = f'attachment; filename="{outer_zip_name}"'
                response["Content-Length"] = zip_size
            
                return response
            except Exception:
                tmp.close()
                os.unlink(tmp.name)
                raise

        except Exception as e:
            _opus_bundle_logger.error("download-opus-bundle failed: %s", e, exc_info=True)
            return Response(
                {"error": "An unexpected error occurred. Please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _build_sample_data_xlsx(self, job, has_opus=True):
        wb = Workbook()
        ws = wb.active
        ws.title = "Flat Table"

        if not has_opus:
            ws.append(["No opus files available for this job."])
            buf = _io.BytesIO()
            wb.save(buf)
            return buf.getvalue()

        scalar_fields = [
            "lab", "material", "instrument", "scan_date", "time", "zone",
            "duration", "operator", "resolution", "zero_filling_factor",
            "number_points", "laser_wavenumber", "wavenumber_one",
            "wavenumber_last", "min_absorbance", "max_absorbance",
        ]

        records = list(
            SampleData.objects.filter(ssn__job_id=job.pk)
            .select_related("ssn")
            .values("ssn__number", *scalar_fields, "other_data")
        )

        seen_keys = set()
        other_keys = []
        for r in records:
            for k in (r.get("other_data") or {}):
                if k not in seen_keys:
                    other_keys.append(k)
                    seen_keys.add(k)

        ws.append(["SSN"] + scalar_fields + other_keys)

        for r in records:
            other_vals = [r.get("other_data", {}).get(k, "") for k in other_keys]
            ws.append([r.get("ssn__number", "")] + [r.get(f, "") for f in scalar_fields] + other_vals)

        buf = _io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def _build_wetchem_xlsx(self, job):
        standard_fields = [
            f.name
            for f in WetChemSampleData._meta.get_fields()
            if not f.is_relation and f.name != "id"
        ]
        extra_columns = list(WetChemColumn.objects.values_list("name", flat=True))
        all_headers = standard_fields + extra_columns

        wb = Workbook()
        ws = wb.active
        ws.title = "Wet Chemistry"

        records = WetChemSampleData.objects.filter(job=job)
        if not records.exists():
            ws.append(["No wet chemistry data available for this job."])
            buf = _io.BytesIO()
            wb.save(buf)
            return buf.getvalue()

        ws.append(all_headers)

        value_map = {
            (wv["ssn"], wv["wetchembridge__column__name"]): wv["value"]
            for wv in WetChemValue.objects.filter(job=job).values(
                "ssn", "wetchembridge__column__name", "value"
            )
        }

        for record in records:
            row = [getattr(record, f, None) for f in standard_fields]
            for col_name in extra_columns:
                row.append(value_map.get((record.ssn, col_name)))
            ws.append(row)

        buf = _io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def _build_login_sheet_xlsx(self, job):
        base_headers = [
            "SSN", "Job No", "Study", "Scientist", "Site",
            "Region", "Country", "Material", "Sampling", "Date",
        ]
        sampling_design = job.get_sampling_design_display()

        try:
            country = pycountry.countries.get(alpha_2=job.country).name
        except Exception:
            country = job.country or ""

        material_parts = []
        for mat_key in ("plant", "soil", "fertilizer", "other"):
            mat_data = getattr(job, mat_key, None) or {}
            try:
                if any(int(v) > 0 for v in mat_data.values()):
                    material_parts.append(mat_key)
            except (ValueError, TypeError):
                pass
        material_str = ",".join(material_parts)

        wb = Workbook()
        ws = wb.active
        ws.title = "Sample List"

        if job.sampling_design == Job.LDSF:
            ldsf_extra = [
                "Cluster", "Plot", "Depth Std", "Depth Top",
                "Depth Bottom", "Air Dried Wt", "Coarse Wt",
            ]
            ws.append(base_headers + ldsf_extra)
            for s in Sample.objects.filter(job=job).select_related("sampleldsfdetail"):
                d = getattr(s, "sampleldsfdetail", None)
                ws.append([
                    s.number, job.job_number, job.project, job.scientist_name,
                    job.site, job.region, country, material_str, sampling_design,
                    str(job.samples_received_on) if job.samples_received_on else "",
                    d.cluster if d else None,
                    d.plot if d else None,
                    d.depth_std if d else None,
                    d.depth_top if d else None,
                    d.depth_bottom if d else None,
                    d.air_dried_wt if d else None,
                    d.coarse_wt if d else None,
                ])
        else:
            custom_fields = list(
                CustomField.objects.filter(jobs=job).values_list("label", flat=True)
            )
            ws.append(base_headers + custom_fields)
            cfv_map = {
                (cfv["field__label"], cfv["sample_id"]): cfv["value"]
                for cfv in CustomFieldValue.objects.filter(sample__job=job).values(
                    "field__label", "sample_id", "value"
                )
            }
            for s in Sample.objects.filter(job=job):
                row = [
                    s.number, job.job_number, job.project, job.scientist_name,
                    job.site, job.region, country, material_str, sampling_design,
                    str(job.samples_received_on) if job.samples_received_on else "",
                ]
                for field_label in custom_fields:
                    row.append(cfv_map.get((field_label, s.pk)))
                ws.append(row)

        buf = _io.BytesIO()
        wb.save(buf)
        return buf.getvalue()


class JobSitesListView(APIView):
    authentication_classes = [DownloadTokenAuthentication]
    permission_classes = [IsAuthenticated]
    """
    GET /jobs/sites
    Returns a list of distinct site names.

    Query params:
        country  (optional) — one or more country names, comma-separated e.g. "Kenya,Uganda"
    """

    def get(self, request):
        country_param = request.GET.get("country", "").strip()

        qs = Job.objects.exclude(site__isnull=True).exclude(site="")

        if country_param:
            if "," in country_param:
                return Response(
                    {"error": "Only one country can be specified at a time."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            match = None
            try:
                match = pycountry.countries.get(name=country_param)
                if not match:
                    match = pycountry.countries.search_fuzzy(country_param)[0]
            except LookupError:
                pass
            if not match:
                return Response(
                    {"error": f"Country not found: {country_param}. Please check the spelling and try again."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(country=match.alpha_2)

        sites = sorted(qs.values_list("site", flat=True).distinct())
        return Response({"sites": sites})


class SpectraQCFlagView(APIView):
    """
    GET  /jobs/spectra-qc-flags/?job_id=&ssn=&is_resolved=
        List QC flags. Regional admins see flags for their organization's jobs.
    POST /jobs/spectra-qc-flags/
        Create a QC flag for a sample.
    PATCH /jobs/spectra-qc-flags/<id>/resolve/
        Mark a flag as resolved.
    """

    permission_classes = [IsAuthenticated]

    def _is_regional_admin(self, user):
        return user.groups.filter(name="Regional Admin").exists()

    def _notify_outlier_tagged(self, sample, request_user, flagged_ssns):
        if not flagged_ssns:
            return

        admin_users = list(CustomUser.objects.filter(is_superuser=True, is_active=True))
        regional_admins = list(
            CustomUser.objects.filter(
                groups__name="Regional Admin",
                organization=sample.job.organization,
                is_active=True,
            )
        )
        recipients = {user.id: user for user in admin_users + regional_admins}.values()
        tagged_at = timezone.now().strftime("%Y-%m-%d %H:%M UTC")
        tagged_by_name = getattr(request_user, "name", str(request_user))
        notifications = [
            {
                "user_to_notify": recipient,
                "notification_type": SPECTRA_OUTLIER_TAGGED,
                "email_subject": f"Spectra outlier tagged - {sample.job.site} ({sample.job.job_number})",
                "email_context": {
                    "name": recipient.name,
                    "job_number": sample.job.job_number,
                    "site": sample.job.site,
                    "flagged_count": len(flagged_ssns),
                    "flagged_ssns": flagged_ssns,
                    "uploaded_by": tagged_by_name,
                    "tagged_at": tagged_at,
                },
            }
            for recipient in recipients
        ]
        if notifications:
            Notification.objects.bulk_create([Notification(**data) for data in notifications])
            send_bulk_emails(notifications)

    def get(self, request):
        if not (self._is_regional_admin(request.user) or request.user.is_superuser):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        qs = SpectraQCFlag.objects.select_related("ssn", "ssn__job", "flagged_by", "resolved_by")

        if not request.user.is_superuser:
            qs = qs.filter(ssn__job__organization=request.user.organization)

        job_id = request.GET.get("job_id")
        ssn = request.GET.get("ssn")
        is_resolved = request.GET.get("is_resolved")

        if job_id:
            qs = qs.filter(ssn__job_id=job_id)
        if ssn:
            qs = qs.filter(ssn__number=ssn)
        if is_resolved is not None:
            qs = qs.filter(is_resolved=is_resolved.lower() == "true")

        data = [
            {
                "id": f.id,
                "ssn": f.ssn.number,
                "job_number": f.ssn.job.job_number,
                "site": f.ssn.job.site,
                "issue_type": f.issue_type,
                "notes": f.notes,
                "flagged_by": f.flagged_by.name if f.flagged_by else None,
                "flagged_at": f.flagged_at,
                "is_resolved": f.is_resolved,
                "resolved_by": f.resolved_by.name if f.resolved_by else None,
                "resolved_at": f.resolved_at,
            }
            for f in qs
        ]
        return Response(data)

    def post(self, request):
        if not (self._is_regional_admin(request.user) or request.user.is_superuser):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        ssn_number = request.data.get("ssn")
        issue_type = request.data.get("issue_type", SpectraQCFlag.OTHER)
        notes = request.data.get("notes", "")

        if not ssn_number:
            return Response({"error": "ssn is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sample = Sample.objects.select_related("job").get(number=ssn_number)
        except Sample.DoesNotExist:
            return Response({"error": f"Sample {ssn_number} not found."}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_superuser and sample.job.organization != request.user.organization:
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        flag = SpectraQCFlag.objects.create(
            ssn=sample,
            flagged_by=request.user,
            issue_type=issue_type,
            notes=notes,
        )
        # if issue_type == SpectraQCFlag.OUTLIER:
            # try:
            #     self._notify_outlier_tagged(sample, request.user, [ssn_number])
            # except Exception:
            #     pass
        return Response(
            {"id": flag.id, "ssn": ssn_number, "issue_type": flag.issue_type, "flagged_at": flag.flagged_at},
            status=status.HTTP_201_CREATED,
        )


class SpectraQCFlagResolveView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            flag = SpectraQCFlag.objects.select_related("ssn__job").get(pk=pk)
        except SpectraQCFlag.DoesNotExist:
            return Response({"error": "Flag not found."}, status=status.HTTP_404_NOT_FOUND)

        if not (request.user.groups.filter(name="Regional Admin").exists() or request.user.is_superuser):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        if not request.user.is_superuser and flag.ssn.job.organization != request.user.organization:
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        flag.is_resolved = True
        flag.resolved_by = request.user
        flag.resolved_at = timezone.now()
        flag.save(update_fields=["is_resolved", "resolved_by", "resolved_at"])
        return Response({"id": flag.id, "is_resolved": True, "resolved_at": flag.resolved_at})
