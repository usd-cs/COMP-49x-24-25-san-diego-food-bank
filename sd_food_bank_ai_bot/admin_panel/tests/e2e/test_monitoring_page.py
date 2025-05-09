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
    and verifies the metrics display and updates.
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
            password="password",
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
        page.fill('input[name="username"]', 'admin')
        page.fill('input[name="password"]', 'password')
        page.click('button[type="submit"]')
        page.wait_for_url(f"{self.live_server_url}/faqs/")

        # Navigate to Monitoring page
        page.click('a[href="/monitoring/"]')
        page.wait_for_url(f"{self.live_server_url}/monitoring/")
        page.screenshot(path="screenshots/monitoring_initial.png")

        # Check initial total
        title = page.text_content('#totalCallsTitle')
        assert title.startswith("Total Calls: ")
        total_initial = int(title.split(': ')[1])
        assert total_initial == 3
        page.screenshot(path="screenshots/total_calls.png")

        # Filter by month and ensure it's updated
        dropdown = page.locator('#granularity')
        dropdown.select_option('month')
        title_text = page.inner_text('#totalCallsTitle')
        month_total = int(title_text.split(': ')[1])
        assert month_total >= 1
        page.screenshot(path="screenshots/monitoring_month.png")

        # Filter by day and ensure it's updated 
        dropdown.select_option('day')
        title_text = page.inner_text('#totalCallsTitle')
        day_total = int(title_text.split(': ')[1])
        assert day_total >= 1
        page.screenshot(path="screenshots/monitoring_day.png")

        dropdown = page.locator('#topic')
        dropdown.select_option('FAQs')
        title_text = page.inner_text('#totalCallsTitle')
        faq_topic = int(title_text.split(': ')[1])
        assert faq_topic == 0
        page.screenshot(path="screenshots/monitoring_topic.png")

        page.close()
