from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from console.services.quota import check_quota, get_quota_status, get_user_quota
from jobs.models import Job


class Phase1QuotaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="quota-phase1", password="testpass")
        self.quota = get_user_quota(self.user)

    def test_monthly_limit_blocks_submission(self):
        self.quota.jobs_per_month = 1
        self.quota.save(update_fields=["jobs_per_month"])

        Job.objects.create(
            owner=self.user,
            runner="boltz-2",
            model_key="stub",
            status=Job.Status.COMPLETED,
            queued_at=timezone.now(),
        )

        allowed, error = check_quota(self.user)

        self.assertFalse(allowed)
        self.assertIn("per month", error)

    def test_quota_status_reports_priority_tier_and_monthly_usage(self):
        self.quota.priority_tier = "priority"
        self.quota.jobs_per_month = 3
        self.quota.save(update_fields=["priority_tier", "jobs_per_month"])

        Job.objects.create(
            owner=self.user,
            runner="boltz-2",
            model_key="stub",
            status=Job.Status.PENDING,
            queued_at=timezone.now(),
        )

        status = get_quota_status(self.user)

        self.assertEqual(status["priority_tier"], "priority")
        self.assertEqual(status["monthly_jobs"]["current"], 1)
        self.assertEqual(status["monthly_jobs"]["max"], 3)
