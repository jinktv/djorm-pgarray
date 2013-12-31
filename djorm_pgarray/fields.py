# -*- coding: utf-8 -*-

import json

from django import forms
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import six
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _

from .utils import parse_array, edit_string_for_array


TYPES = {
    'int': int,
    'smallint': int,
    'bigint': int,
    'text': str,
    'double precision': float,
    'varchar': str,
}


def _cast_to_unicode(data, force=False):
    if isinstance(data, (list, tuple)):
        return [_cast_to_unicode(x, force) for x in data]
    elif isinstance(data, six.string_types) or force:
        return force_text(data)
    return data


def _cast_to_type(data, type_cast):
    if isinstance(data, (list, tuple)):
        return [_cast_to_type(x, type_cast) for x in data]
    if type_cast == str:
        return force_text(data)
    return type_cast(data)


def _unserialize(value):
    if not isinstance(value, six.string_types):
        return _cast_to_unicode(value)

    try:
        return _cast_to_unicode(json.loads(value))
    except ValueError:
        return _cast_to_unicode(value)


class ArrayField(models.Field):
    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        self._array_type = kwargs.pop('dbtype', 'int')
        type_key = self._array_type.split('(')[0]

        if "type_cast" in kwargs:
            self._type_cast = kwargs.pop("type_cast")
        elif type_key in TYPES:
            self._type_cast = TYPES[type_key]
        else:
            self._type_cast = lambda x: x

        self._dimension = kwargs.pop('dimension', 1)
        kwargs.setdefault('blank', True)
        kwargs.setdefault('null', True)
        kwargs.setdefault('default', None)
        super(ArrayField, self).__init__(*args, **kwargs)

    def formfield(self, **params):
        params.setdefault('form_class', ArrayFormField)
        return super(ArrayField, self).formfield(**params)

    def db_type(self, connection):
        return '{0}{1}'.format(self._array_type, "[]" * self._dimension)

    def get_db_prep_value(self, value, connection, prepared=False):
        value = value if prepared else self.get_prep_value(value)
        if not value or isinstance(value, six.string_types):
            return value
        return _cast_to_type(value, self._type_cast)

    def get_prep_value(self, value):
        return value

    def to_python(self, value):
        return _unserialize(value)

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return _cast_to_unicode(self.get_prep_value(value), True)

    def validate(self, value, model_instance):
        for val in value:
            super(ArrayField, self).validate(val, model_instance)


# South support
try:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([
        (
            [ArrayField], # class
            [], # positional params
            {
                "dbtype": ["_array_type", {"default": "int"}],
                "dimension": ["_dimension", {"default": 1}],
            }
        )
    ], ['^djorm_pgarray\.fields\.ArrayField'])
except ImportError:
    pass


class ArrayFormField(forms.Field):
    widget = forms.TextInput

    def __init__(self, *args, **kwargs):
        self.item_field = kwargs.pop('item_field', None)
        return super(ArrayFormField, self).__init__(*args, **kwargs)

    def prepare_value(self, value):
        if value is not None and not isinstance(value, six.string_types):
            if self.item_field:
                value = [self.item_field.prepare_value(item_val) for item_val in value]
            value = edit_string_for_array(value)
        return value

    def to_python(self, value):
        if isinstance(value, six.string_types):
            try:
                return parse_array(value)
            except ValueError:
                raise forms.ValidationError(_("Please provide a comma-separated list of values."))
        else:
            return value

    def clean(self, value):
        value = super(ArrayFormField, self).clean(value)
        if self.item_field:
            return [self.item_field.clean(item_val) for item_val in value]
        return value

class SetFormField(ArrayFormField):
    def to_python(self, value):
        if value is None:
            return value
        val = list(set(super(SetFormField, self).to_python(value)))
        val.sort()
        return val
