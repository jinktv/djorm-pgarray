# -*- coding: utf-8 -*-
from django import forms
from django.db import models
from django.utils.encoding import force_unicode
from .utils import parse_array, edit_string_for_array


class ArrayFormField(forms.Field):
    widget = forms.TextInput
    def prepare_value(self, value):
        if value is not None and not isinstance(value, basestring):
            value = edit_string_for_array(value)
        return value
    def to_python(self, value):
        if isinstance(value, basestring):
            try:
                return parse_array(value)
            except ValueError:
                raise forms.ValidationError(_("Please provide a comma-separated list of values."))
        else:
            return value

def _cast_to_unicode(data):
    if isinstance(data, (list, tuple)):
        return [_cast_to_unicode(x) for x in data]
    elif isinstance(data, str):
        return force_unicode(data)
    return data


class ArrayField(models.Field):
    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        self._array_type = kwargs.pop('dbtype', 'int')
        self._dimension = kwargs.pop('dimension', 1)
        kwargs.setdefault('blank', True)
        kwargs.setdefault('null', True)
        kwargs.setdefault('default', None)
        super(ArrayField, self).__init__(*args, **kwargs)

    def db_type(self, connection):
        return '{0}{1}'.format(self._array_type, "[]" * self._dimension)

    def get_db_prep_value(self, value, connection, prepared=False):
        value = value if prepared else self.get_prep_value(value)
        if not value or isinstance(value, basestring):
            return value

        return value

    def get_prep_value(self, value):
        return value

    def to_python(self, value):
        return _cast_to_unicode(value)

    def formfield(self, **kwargs):
        # Passing max_length to forms.CharField means that the value's length
        # will be validated twice. This is considered acceptable since we want
        # the value in the form field (to pass into widget for example).
        defaults = {'form_class': ArrayFormField}
        defaults.update(kwargs)
        return super(ArrayField, self).formfield(**defaults)

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