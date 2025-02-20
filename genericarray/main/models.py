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
    my = GenericArrayForeignKey(
        field="data"
    )

    data = models.CharField(max_length=1000)