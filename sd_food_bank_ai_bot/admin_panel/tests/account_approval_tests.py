from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import Permission
from admin_panel.models import Admin
from django.utils.http import urlencode


class AccountApprovalViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

        # Admins for testing permissions
        self.no_perm_user = Admin.objects.create_user(
            username='noperm', password='pass123', approved_for_admin_panel=True
        )

        self.perm_user = Admin.objects.create_user(
            username='approved', password='pass123', approved_for_admin_panel=True
        )
        permission = Permission.objects.get(codename='can_approve_users')
        self.perm_user.user_permissions.add(permission)

        # Admins for testing page
        self.admin_1 = Admin.objects.create(
            foodbank_id="1234", foodbank_email="admin_1@sdfb.com",
            username="admin_1", approved_for_admin_panel=None
        )
        self.admin_2 = Admin.objects.create(
            foodbank_id="4321", foodbank_email="admin_2@sdfb.com",
            username="admin_2", approved_for_admin_panel=True
        )
        self.admin_3 = Admin.objects.create(
            foodbank_id="2413", foodbank_email="admin_3@sdfb.com",
            username="admin_3",approved_for_admin_panel=False
        )

    def test_account_approval_page_no_permission(self):
        """
        Check that the account approval page cannot be accessed with out permission.
        """
        self.client.force_login(self.no_perm_user)
        response = self.client.get(reverse("account_approval"))
        self.assertEqual(response.status_code, 403)

    def test_account_approval_permission(self):
        """
        Check that the account approval page can be accessed with permission.
        """
        self.client.force_login(self.perm_user)
        response = self.client.get(reverse("account_approval"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account_approval.html")

    def test_account_approval_search_and_filter(self):
        """
        Test the search and filter features of the account approval page.
        """
        self.client.force_login(self.perm_user)
        query = urlencode({'q': '4321', 'status': 'True'})
        response = self.client.get(f"{reverse('account_approval')}?{query}")
        self.assertContains(response, "admin_2@sdfb.com")
        self.assertNotContains(response, "admin_1@sdfb.com")
        self.assertNotContains(response, "admin_3@sdfb.com")

    def test_approve_account(self):
        """
        Test that an account properly receives approval.
        """
        self.client.force_login(self.perm_user)
        response = self.client.post(reverse("approve_account", args=[self.admin_1.id]))
        self.assertRedirects(response, reverse("account_approval"))
        self.admin_1.refresh_from_db()
        self.assertTrue(self.admin_1.approved_for_admin_panel)

    def test_deny_account(self):
        """
        Test that an account is properly denied.
        """
        self.client.force_login(self.perm_user)
        response = self.client.post(reverse("deny_account", args=[self.admin_2.id]))
        self.assertRedirects(response, reverse("account_approval"))
        self.admin_2.refresh_from_db()
        self.assertIsNone(self.admin_2.approved_for_admin_panel)

    def test_delete_account(self):
        """
        Test that an account is properly deleted.
        """
        self.client.force_login(self.perm_user)
        response = self.client.post(reverse("delete_account", args=[self.admin_3.id]))
        self.assertRedirects(response, reverse("account_approval"))
        self.assertFalse(Admin.objects.filter(id=self.admin_3.id).exists())

    def test_add_account_page_get(self):
        """
        Check that add account page loads.
        """
        self.client.force_login(self.perm_user)
        response = self.client.get(reverse("add_account_page"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'add_account.html')

    def test_add_account_page_post_valid(self):
        """
        Check add account page adds user to the database.
        """
        self.client.force_login(self.perm_user)
        data = {
            'foodbank_email': 'new@fb.org',
            'foodbank_id': '1357'
        }
        response = self.client.post(reverse("add_account_page"), data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Admin.objects.filter(foodbank_email='new@fb.org').exists())