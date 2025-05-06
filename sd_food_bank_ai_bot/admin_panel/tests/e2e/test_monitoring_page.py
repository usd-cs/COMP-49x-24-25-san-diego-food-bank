# admin_panel/tests/test_monitoring_page_e2e.py
import os
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.utils import timezone
from datetime import timedelta
from playwright.sync_api import sync_playwright
from admin_panel.models import Log, Admin

class MonitoringPageE2ETest(StaticLiveServerTestCase):
    """
    End-to-end test for the monitoring dashboard. Logs in, navigates to Monitoring,
    and verifies the Total Calls metric displays and updates for each granularity.
    """
    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        self.user = Admin.objects.create_user(
            username="admin",
            password="admin",
            foodbank_email="bbost@sandiego.edu",
            foodbank_id="9876",
            approved_for_admin_panel=True
        )
        now = timezone.now()
        Log.objects.create(phone_number="+15550000001", time_started=now - timedelta(days=365))
        Log.objects.create(phone_number="+15550000002", time_started=now - timedelta(days=30))
        Log.objects.create(phone_number="+15550000003", time_started=now)

    def test_monitoring_page_displays_and_filters(self):
        page = self.browser.new_page()

        # Log in
        page.goto(f"{self.live_server_url}/login/")
        page.fill('input[name="username"]', 'bbost')
        page.fill('input[name="password"]', 'password')
        page.click('button[type="submit"]')
        page.wait_for_url(f"{self.live_server_url}/faqs/")

        # Navigate to Monitoring page
        page.click('a[href="/monitoring/"]')
        page.wait_for_url(f"{self.live_server_url}/monitoring/")
        page.screenshot(path="screenshots/monitoring_initial.png")

        # Check initial total
        title = page.text_content('#totalCallsTitle')
        assert title.startswith("Total Calls: "), f"Unexpected title: {title}"
        total_initial = int(title.split(': ')[1])
        assert total_initial == 3, "Expected 3 seeded logs"

        # Filter by month and ensure it's updated
        page.select_option('#granularity', 'month')
        page.wait_for_response(lambda r: '/api/total-calls/' in r.url and 'granularity=month' in r.url)
        page.screenshot(path="screenshots/monitoring_month.png")
        month_total = int(page.text_content('#totalCallsTitle').split(': ')[1])
        assert month_total >= 1, "Month filter should return at least one log"

        # Filter by day and ensure it's updated 
        page.select_option('#granularity', 'day')
        page.wait_for_response(lambda r: '/api/total-calls/' in r.url and 'granularity=day' in r.url)
        page.screenshot(path="screenshots/monitoring_day.png")
        day_total = int(page.text_content('#totalCallsTitle').split(': ')[1])
        assert day_total >= 1, "Day filter should return today's log"

        page.close()
