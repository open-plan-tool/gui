from users.views import user_info
from django.contrib.auth.models import AnonymousUser
from django.test.client import RequestFactory
from django.urls import reverse
from users.forms import CustomUserChangeForm, CustomUserCreationForm
from django.test import TestCase, override_settings
from users.models import CustomUser

# Create your tests here.


class UserModelTest(TestCase):
    @classmethod
    def SetUpTestData(cls):
        # Set up non-modified objects used by all test methods
        pass

    def setUp(self):
        # Set up for every test method in the test class
        self.factory = RequestFactory()
        test_user = CustomUser.objects.create_user(
            username="testUser",
            email="testUser@name.email",
            password="ASas12,.",
            first_name="ICOM",
            last_name="Tester",
        )
        test_user.save()

    """
    Models Tests
    """

    def test_user_model(self):
        CustomUser.objects.create(
            username="username", email="user@name.email", password="ASas12,."
        ).save()
        created_user = CustomUser.objects.get(username="username")
        self.assertIsNotNone(created_user)

    """
    Forms Tests
    """

    def test_user_create_form(self):
        form = CustomUserCreationForm(
            data={
                "email": "test@dummyemail.com",
                "first_name": "some",
                "last_name": "user",
                "username": "someUser",
                "password1": "ASas12,.",
                "password2": "ASas12,.",
                "accept_privacy": True,
            }
        )
        self.assertTrue(form.is_valid())

    def test_user_change_form(self):
        form = CustomUserChangeForm(
            data={
                "email": "test2@dummyemail.com",
                "first_name": "some",
                "last_name": "user",
                "username": "someUser",
            }
        )
        self.assertTrue(form.is_valid())

    """
    Views Tests
    """

    # Signup
    def test_view_url_exists_at_desired_location(self):
        response = self.client.get("/en/users/signup/")
        self.assertEqual(response.status_code, 200)

    def test_signup_view_url_accessible_by_name(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)

    def test_signup_view_uses_correct_template(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/signup.html")

    # user_info
    def test_redirect_if_not_logged_in(self):
        response = self.client.get(reverse("user_info"))
        self.assertRedirects(response, "/en/users/login/?next=/en/users/user_info/")

    def test_logged_in_user_can_access_self_user_info_view(self):
        request = self.factory.get(reverse("user_info"))
        test_user = CustomUser.objects.get(username="testUser")
        request.user = test_user

        response = user_info(request)
        self.assertEqual(response.status_code, 200)

    def test_anonymus_user_can_not_access_self_user_info_view(self):
        request = self.factory.get(reverse("user_info"))
        request.user = AnonymousUser()

        response = user_info(request)
        self.assertEqual(
            response.status_code, 302
        )  # check if the Anonymous User is redirected to login

    # @override_settings(LOGIN_URL='/users/login/')
    def test_user_login(self):
        login_response = self.client.login(username="testUser", password="ASas12,.")
        self.assertTrue(login_response)
