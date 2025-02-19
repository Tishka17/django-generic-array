import json
import warnings
from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.db.models.fields import Field
from django.db.models.fields.mixins import FieldCacheMixin
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.functional import cached_property


class TerminationGenericForeignKey(FieldCacheMixin, Field):
    """
    Provide a generic many-to-one relation through the ``content_type`` and
    ``object_id`` fields.

    This class also doubles as an accessor to the related object (similar to
    ForwardManyToOneDescriptor) by adding itself as a model attribute.
    """

    many_to_many = True
    many_to_one = False
    one_to_many = False
    one_to_one = False

    def __init__(
            self, field, for_concrete_model=True
    ):
        super().__init__(editable=False)
        self.field = field
        self.for_concrete_model = for_concrete_model
        self.is_relation = True

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, private_only=True, **kwargs)
        # GenericForeignKey is its own descriptor.
        setattr(cls, self.attname, self)

    def get_attname_column(self):
        attname, column = super().get_attname_column()
        return attname, None

    @cached_property
    def cache_name(self):
        return self.name

    def _get_ids(self, instance):
        ct_attname = self.model._meta.get_field(self.field).attname
        related = getattr(instance, ct_attname)
        if not related:
            return []
        related = json.loads(related)
        if not related:
            return []
        termination = related[-1]
        if not termination:
            return []
        # type, id
        return termination

    def get_content_type(self, obj=None, id=None, using=None, model=None):
        if obj is not None:
            return ContentType.objects.db_manager(obj._state.db).get_for_model(
                obj, for_concrete_model=self.for_concrete_model
            )
        elif id is not None:
            return ContentType.objects.db_manager(using).get_for_id(id)
        elif model is not None:
            return ContentType.objects.db_manager(using).get_for_model(
                model, for_concrete_model=self.for_concrete_model
            )
        else:
            # This should never happen. I love comments like this, don't you?
            raise Exception("Impossible arguments to GFK.get_content_type!")

    def get_prefetch_queryset(self, instances, queryset=None):
        warnings.warn(
            "get_prefetch_queryset() is deprecated. Use get_prefetch_querysets() "
            "instead.",
            RemovedInDjango60Warning,
            stacklevel=2,
        )
        if queryset is None:
            return self.get_prefetch_querysets(instances)
        return self.get_prefetch_querysets(instances, [queryset])

    def get_prefetch_querysets(self, instances, querysets=None):
        custom_queryset_dict = {}
        if querysets is not None:
            for queryset in querysets:
                ct_id = self.get_content_type(
                    model=queryset.query.model, using=queryset.db
                ).pk
                if ct_id in custom_queryset_dict:
                    raise ValueError(
                        "Only one queryset is allowed for each content type."
                    )
                custom_queryset_dict[ct_id] = queryset

        # For efficiency, group the instances by content type and then do one
        # query per model
        fk_dict = defaultdict(set)
        # We need one instance for each group in order to get the right db:
        instance_dict = defaultdict(list)
        ct_attname = self.model._meta.get_field(self.field).attname
        for instance in instances:
            for ct_id, fk_val in self._get_ids(instance):
                fk_dict[ct_id].add(fk_val)
                instance_dict[ct_id].append(instance)

        ret_val = []
        for ct_id, fkeys in fk_dict.items():
            if ct_id in custom_queryset_dict:
                # Return values from the custom queryset, if provided.
                ret_val.extend(custom_queryset_dict[ct_id].filter(pk__in=fkeys))
            else:
                # FIXME
                instance = instance_dict[ct_id]
                ct = self.get_content_type(id=ct_id, using=instance._state.db)
                ret_val.extend(ct.get_all_objects_for_this_type(pk__in=fkeys))

        def gfk_inst(obj):
            return lists_keys[id(obj)]

        def gfk_key(obj):
            ct_id = getattr(obj, ct_attname)
            if ct_id is None:
                return None
            else:
                result = tuple(sorted(map(tuple, self._get_ids(instance))))
                return result

        to_store = defaultdict(list)
        lists = []
        lists_keys = {}
        for instance in instances:
            data = []
            lists.append(data)
            lists_keys[id(data)] = gfk_key(instance)
            for ct, fk in self._get_ids(instance):
                to_store[ct, fk].append(data)

        for rel_obj in ret_val:
            ct = self.get_content_type(obj=rel_obj).pk
            for data in to_store[ct, rel_obj.pk]:
                data.append(rel_obj)

        return (
            lists,
            gfk_inst,
            gfk_key,
            True,
            self.cache_name,
            True,
        )

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        return instance.__dict__[self.name]

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value
        return
