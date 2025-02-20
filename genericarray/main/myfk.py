import json
from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.fields import Field
from django.db.models.fields.mixins import FieldCacheMixin
from django.utils.functional import cached_property


class GenericArrayForeignKey(FieldCacheMixin, Field):
    """
    Provide a generic many-to-many relation through an array field
    """

    many_to_many = True
    many_to_one = False
    one_to_many = False
    one_to_one = False

    def __init__(self, field, for_concrete_model=True):
        super().__init__(editable=False)
        self.field = field
        self.for_concrete_model = for_concrete_model
        self.is_relation = True

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, private_only=True, **kwargs)
        # GenericForeignKey is its own descriptor.
        setattr(cls, self.attname, self)

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

    def get_content_type_by_id(self, id=None, using=None):
        return ContentType.objects.db_manager(using).get_for_id(id)

    def get_content_type_of_obj(self, obj=None):
        return ContentType.objects.db_manager(obj._state.db).get_for_model(
            obj, for_concrete_model=self.for_concrete_model
        )

    def get_content_type_for_model(self, using=None, model=None):
        return ContentType.objects.db_manager(using).get_for_model(
            model, for_concrete_model=self.for_concrete_model
        )

    def get_prefetch_querysets(self, instances, querysets=None):
        custom_queryset_dict = {}
        if querysets is not None:
            for queryset in querysets:
                ct_id = self.get_content_type_for_model(
                    model=queryset.query.model, using=queryset.db
                ).pk
                if ct_id in custom_queryset_dict:
                    raise ValueError(
                        "Only one queryset is allowed for each content type."
                    )
                custom_queryset_dict[ct_id] = queryset

        # For efficiency, group the instances by content type and then do one
        # query per model
        fk_dict = defaultdict(set)  # type id, db -> model ids
        for instance in instances:
            for ct_id, fk_val in self._get_ids(instance):
                fk_dict[(ct_id, instance._state.db)].add(fk_val)

        rel_objects = []
        for (ct_id, db), fkeys in fk_dict.items():
            if ct_id in custom_queryset_dict:
                rel_objects.extend(custom_queryset_dict[ct_id].filter(pk__in=fkeys))
            else:
                ct = self.get_content_type_by_id(id=ct_id, using=db)
                rel_objects.extend(ct.get_all_objects_for_this_type(pk__in=fkeys))

        # reorganize objects to fix usage
        items = {
            (self.get_content_type_of_obj(obj=rel_obj).pk, rel_obj.pk, rel_obj._state.db): rel_obj
            for rel_obj in rel_objects
        }
        lists = []
        lists_keys = {}
        for instance in instances:
            data = []
            lists.append(data)
            lists_keys[instance] = id(data)
            for ct, fk in self._get_ids(instance):
                if rel_obj := items.get((ct, fk, instance._state.db)):
                    data.append(rel_obj)

        return (
            lists,
            lambda obj: id(obj),
            lambda obj: lists_keys[obj],
            True,
            self.cache_name,
            False,
        )

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        rel_objects = self.get_cached_value(instance, default=None)
        expected_ids = self._get_ids(instance)
        #check cache actual
        if rel_objects is not None:
            actual = [
                [self.get_content_type_of_obj(obj=item).id, item.pk]
                for item in rel_objects
            ]
            if expected_ids == actual:
                return rel_objects
        # reload value
        if expected_ids is None:
            self.set_cached_value(instance, rel_objects)
            return rel_objects
        rel_objects = []
        for ct_id, pk_val in self._get_ids(instance):
            ct = self.get_content_type_by_id(id=ct_id, using=instance._state.db)
            try:
                rel_obj = ct.get_object_for_this_type(
                    using=instance._state.db, pk=pk_val
                )
                rel_objects.append(rel_obj)
            except ObjectDoesNotExist:
                print("__get__ ObjectDoesNotExist", ct_id, pk_val)
                pass
        self.set_cached_value(instance, rel_objects)
        return rel_objects

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value
