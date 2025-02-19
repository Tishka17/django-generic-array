from django.core.management import BaseCommand
from django.db import transaction

from main.genprefetch import GenericPrefetch
from main.models import A, B, C


def add():
    print("Adding data")
    transaction.set_autocommit(False)
    aforb = A(id=1000, title="A for B")
    aforb.save(force_insert=True)
    a = A(id=1, title="A1")
    a.save(force_insert=True)
    b1 = B(id=1, title="B1", desc="b1", a=aforb)
    b1.save(force_insert=True)
    b2 = B(id=2, title="B2", desc="b2", a=aforb)
    b2.save(force_insert=True)

    c = C(id=1, title="C0", termination=b1)
    c.data = [[[c.type.id, c.fk]]]
    c.save(force_insert=True)
    c1 = C(id=2, title="C1", termination=b2)
    c1.data = [[[c.type.id, c.fk], [c1.type.id, c1.fk]]]
    c1.save(force_insert=True)
    c2 = C(id=3, title="C2", termination=a)
    c2.data = [[[c2.type.id, c2.fk], [c1.type.id, c1.fk]]]
    c2.save(force_insert=True)


def read():
    print("Result")
    q = C.objects.prefetch_related(
        # "my",
        GenericPrefetch(
            "my",
            [
                A.objects.all(),
                B.objects.select_related("a").all(),
            ],
            # to_attr="my2"
        ),
    )
    print("fetch list")
    cs = list(q.all())
    print("iterate")
    for c in cs:
        print("~~~", c.id, c.title)
        print(c.data)
        # print("C: ", c.fk, c.termination)
        # print("TA:", getattr(c.termination, "a", "-"))
        print("Data found:")
        for model in c.my:
            print("   - Related: ", repr(model))
            print("      with A:", getattr(model, "a", "-"))


class Command(BaseCommand):
    help = "check me now"

    def handle(self, *args, **kwargs):
        print("Starting mine")
        add()
        # transaction.commit()
        print("====")
        read()
        transaction.rollback()
        print("Stop mine")
