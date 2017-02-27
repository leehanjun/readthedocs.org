"""Integration with external services"""

import json
import uuid

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from jsonfield import JSONField
from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import HtmlFormatter


class HttpTransactionManager(models.Manager):

    """HTTP manager methods"""

    def from_transaction(self, req, resp, source=None, related_object=None):
        """Create object from Django request and response objects"""
        request_body = req.data if hasattr(req, 'data') else req.body
        if 'payload' in request_body:
            request_body = {'payload': json.loads(request_body['payload'])}
        try:
            request_body = json.dumps(request_body)
        except TypeError:
            pass
        response_body = resp.data if hasattr(resp, 'data') else resp.content
        try:
            response_body = json.dumps(response_body)
        except TypeError:
            pass
        fields = {
            'status_code': resp.status_code,
            # This is the rawest form of request header we have, the WSGI
            # headers. HTTP headers are prefixed with `HTTP_`, which we remove,
            # and because the keys are all uppercase, we'll normalize them to
            # title case-y hyphen separated values.
            'request_headers': dict(
                (key[5:].title().replace('_', '-'), str(val))
                for (key, val) in req.META.items()
                if key.startswith('HTTP_')
            ),
            'request_body': request_body,
            'response_headers': dict(resp.items()),
            'response_body': response_body,
        }
        if source is not None:
            fields['source'] = source
        if related_object is not None:
            fields['related_object'] = related_object
        return self.create(**fields)


class HttpTransaction(models.Model):

    """Record an HTTP transaction"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    related_object = GenericForeignKey('content_type', 'object_id')

    date = models.DateTimeField(_('Date'), auto_now_add=True)

    request_headers = JSONField(_('Request headers'), )
    request_body = models.TextField(_('Request body'))

    response_headers = JSONField(_('Request headers'), )
    response_body = models.TextField(_('Response body'))

    status_code = models.IntegerField(_('Status code'))

    objects = HttpTransactionManager()

    @property
    def failed(self):
        return self.status_code >= 300 or self.status_code < 200

    def formatted_json(self, field):
        value = getattr(self, field) or ''
        try:
            json_value = json.dumps(json.loads(value), sort_keys=True, indent=2)
        except (ValueError, TypeError):
            json_value = value
        formatter = HtmlFormatter(style='friendly')
        ret = highlight(json_value, JsonLexer(), formatter)
        style = '<style>' + formatter.get_style_defs() + '</style>'
        return mark_safe(style + ret)

    @property
    def formatted_request_body(self):
        return self.formatted_json('request_body')

    @property
    def formatted_response_body(self):
        return self.formatted_json('response_body')
