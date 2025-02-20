import json

from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models

from main.myfk import GenericArrayForeignKey


# Create your models here.
class A(models.Model):
    title = models.CharField(max_length=100)


class B(models.Model):
    title = models.CharField(max_length=100)
    desc = models.TextField()
    a = models.ForeignKey(A, on_delete=models.CASCADE, null=True)


class C(models.Model):
    title = models.CharField(max_length=100)
    type = models.ForeignKey(
        to='contenttypes.ContentType',
        on_delete=models.PROTECT,
        related_name='+'
    )
    fk = models.PositiveBigIntegerField()

    termination = GenericForeignKey(
        ct_field='type',
        fk_field='fk'
    )
    data = models.CharField(max_length=1000)

    @property
    def data_unpacked(self):
        return json.loads(self.data)

    @data_unpacked.setter
    def data_unpacked(self, data):
        self.data = json.dumps(data)

    my = GenericArrayForeignKey(
        field="data_unpacked"
    )
