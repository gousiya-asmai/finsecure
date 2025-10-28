import multiprocessing
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Run Django Q cluster with multiprocessing spawn fix for Windows."

    def handle(self, *args, **kwargs):
        multiprocessing.set_start_method('spawn', force=True)
        from django_q.cluster import Cluster
        cluster = Cluster()
        cluster.start()
