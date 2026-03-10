from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class Phase4ConsoleSidebarMigrationTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="ops-phase4",
            password="testpass",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)

    def test_dashboard_uses_shared_sidebar_layout(self):
        response = self.client.get(reverse("console:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "console/base.html")
        self.assertTemplateUsed(response, "base_sidebar.html")
        self.assertContains(response, 'data-sidebar-group="console"', html=False)
        self.assertContains(
            response,
            'href="/console/" class="ui-sidebar-item ui-sidebar-item-active"',
            html=False,
        )

    def test_console_jobs_page_marks_console_jobs_nav_active(self):
        response = self.client.get(reverse("console:job_list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "console/jobs/list.html")
        self.assertTemplateUsed(response, "base_sidebar.html")
        self.assertContains(
            response,
            'href="/console/jobs/" class="ui-sidebar-item ui-sidebar-item-active"',
            html=False,
        )

    def test_console_users_page_marks_users_nav_active(self):
        response = self.client.get(reverse("console:user_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'href="/console/users/" class="ui-sidebar-item ui-sidebar-item-active"',
            html=False,
        )
