"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase
from tests.factories import AccountFactory
from service.common import status  # HTTP Status Codes
from service.models import db, Account, init_db
from service.routes import app
from service import talisman
DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)

BASE_URL = "/accounts"
HTTPS_ENVIRON = {'wsgi.url_scheme': 'https'}


######################################################################
#  T E S T   C A S E S
######################################################################
class TestAccountService(TestCase):
    """Account Service Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)
        talisman.force_https = False

    @classmethod
    def tearDownClass(cls):
        """Runs once before test suite"""

    def setUp(self):
        """Runs before each test"""
        db.session.query(Account).delete()  # clean up the last tests
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Runs once after each test case"""
        db.session.remove()

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_accounts(self, count):
        """Factory method to create accounts in bulk"""
        accounts = []
        for _ in range(count):
            account = AccountFactory()
            response = self.client.post(BASE_URL, json=account.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test Account",
            )
            new_account = response.get_json()
            account.id = new_account["id"]
            accounts.append(account)
        return accounts

    ######################################################################
    #  A C C O U N T   T E S T   C A S E S
    ######################################################################

    def test_index(self):
        """It should get 200_OK from the Home Page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health(self):
        """It should be healthy"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "OK")

    def test_create_account(self):
        """It should Create a new Account"""
        account, response = self.create_mock_account()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_account = response.get_json()
        self.compare_account_and_dict(account, new_account)

    def test_bad_request(self):
        """It should not Create an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_media_type(self):
        """It should not Create an Account when sending the wrong media type"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="test/html"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # ADD YOUR TEST CASES HERE ...
    def test_list_accounts(self):
        """List Accounts should not return 404, should return array of accounts (even empty array)"""
        response = self.client.get(
            BASE_URL
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        print(response.get_json())
        self.assertEqual(0, len(response.get_json()[0]))

    def test_read_account_successful(self):
        account, response = self.create_mock_account()
        web_response = self.read_account(account.id)
        print(web_response)
        self.assertNotEqual(status.HTTP_404_NOT_FOUND, web_response.status_code, "returned 404")
        new_account = web_response.get_json()
        self.compare_account_and_dict(account, new_account)

    def test_update_success(self):
        """Update should find an account and change it in the database"""
        # create account in db, change the account, update
        (account1, response1) = self.create_mock_account()
        account2 = AccountFactory()

        response2 = self.client.post(BASE_URL+"/"+str(response1.get_json()["id"]),
                                     json=account2.serialize(), content_type="application/json")

        self.assertNotEqual(status.HTTP_404_NOT_FOUND, response2.status_code)
        account_json = response2.get_json()
        print(account_json)
        self.compare_account_and_dict(account2, account_json[0])

    def test_delete(self):
        """tests idempotence and whether the count of the accounts decremented by 1"""

        (account1, response1) = self.create_mock_account()
        stuff = self.client.get(BASE_URL).get_json()
        print(stuff)
        initial_length = len(
            stuff[0]
        )
        id = response1.get_json()["id"]
        self.client.delete(BASE_URL + "/" + str(id))
        self.assertNotEqual(initial_length, len(Account.all()))
        self.client.delete(BASE_URL + "/" + str(id))
        self.assertEqual(initial_length-1, len(Account.all()))

    def test_security_headers(self):
        """It should return security headers"""
        headers = {
            'X-Frame-Options': 'SAMEORIGIN',
            'X-XSS-Protection': '1; mode=block',
            'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': 'default-src \'self\'; object-src \'none\'',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }
        response = self.client.get("/", environ_overrides=HTTPS_ENVIRON)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in headers.keys():
            self.assertEqual(response.headers.get(key), headers[key])

    def test_security_headers_2(self):
        """It should test the security headers"""
        response = self.client.get("/", environ_overrides=HTTPS_ENVIRON)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")

    def test_error_handlers(self):
        """Should test the 404 and 405 error handlers"""
        response = self.client.get("butts")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.delete(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def compare_account_and_dict(self, account, dict):
        self.assertEqual(dict["email"], account.email, "email mismatch")
        self.assertEqual(dict["name"], account.name,  "name mismatch")
        self.assertEqual(dict["address"], account.address, "address mismatch")
        self.assertEqual(dict["phone_number"], account.phone_number, "phone_number mismatch")
        self.assertEqual(dict["date_joined"], str(account.date_joined), "date_joined mismatch")

    def create_mock_account(self):
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        account.id = response.get_json()["id"]
        return (account, response)

    def read_account(self, id):
        return self.client.get(BASE_URL+"/"+str(id))
