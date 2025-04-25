import os
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from datetime import timedelta
from django.utils import timezone
from playwright.sync_api import sync_playwright
from admin_panel.models import Log, Admin

class AuditLogsE2ETest(StaticLiveServerTestCase):
    """
    End-to-end test for the audit log page. Navigates throug teh login page to the faq page and finally ends at the audit log page where it confirms the dummy log is there and all relevant information is displayed as intended
    """
    @classmethod
    def setUpClass(cls):
        """Set up browser and playwright instance for e2e test"""
        # Fixes async with synchronous issue since django executes synchronously but playwright is asynchronous
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        # starts a browser instance for playwright
        cls.playwright = sync_playwright().start()
        # turn off gui display of browser
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        """Kill resources used for e2e test by playwright"""
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        """Create necessary dummy objects for e2e test of audit logs"""
        # Create a test admin and log entry in the database.
        self.user = Admin.objects.create_user(
            foodbank_email = "evanscott@sandiego.edu",
            username = "evanscott",
            password = "hardp123",
            foodbank_id = "1234",
            approved_for_admin_panel = True
            )
        self.log_entry = Log.objects.create(
            phone_number="+1234567890",
            transcript = [{'message': 'Thank you!', 'speaker': 'bot'}, {'message': 'Your welcome!', 'speaker': 'caller'}],
            time_started = timezone.now(),
            length_of_call = timedelta(minutes=10)
            )

    def test_audit_log_entry_appears(self):
        """Navigate through admin panel to audit logs and verify all relevant information is displaying as intended"""
        page = self.browser.new_page()

        page.goto(f"{self.live_server_url}/login/")
        page.screenshot(path="screenshots/login_empty.png")
        page.fill('input[name="username"]', 'evanscott')
        page.fill('input[name="password"]', 'hardp123')
        page.screenshot(path="screenshots/login_filled.png")
        page.click('button[type="submit"]')

        page.wait_for_url(f"{self.live_server_url}/faqs/")
        page.screenshot(path="screenshots/faq.png")
        page.click('a[href="/audit_logs/"]')
        page.wait_for_url(f"{self.live_server_url}/audit_logs/")
        page.screenshot(path="screenshots/audit_logs.png")

        content = page.content()
        assert "+1234567890" in content, "Expected phone number not found"
        assert "0:10:00" in content, "Expected call duration not found"

        page.fill('input[name="q"]', '+1234567890')
        page.click('button.search-button')

        page.wait_for_url(f"{self.live_server_url}/audit_logs/?q=%2B1234567890&date=")
        page.screenshot(path="screenshots/audit_logs_filtered.png")

        filtered_rows = page.query_selector_all("table tbody tr")
        assert len(filtered_rows) == 1, "Search should return exactly one result"

        assert "+1234567890" in content, "Expected phone number not found"
        assert "0:10:00" in content, "Expected call duration not found"

        filtered_rows[0].click()
        page.wait_for_url(f"{self.live_server_url}/single_log_view/{self.log_entry.id}/")
        page.screenshot(path="screenshots/single_log_view.png")

        page_content = page.content()
        assert "Thank you!" in page_content, "Expected transcript message from bot not found"
        assert "Your welcome!" in page_content, "Expected transcript message from caller not found"

        page.close()
