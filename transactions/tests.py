
# Create your tests here.
# transactions/tests.py

from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Transaction

class TransactionTests(TestCase):

    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(username='testuser', password='pass1234')
        self.client.login(username='testuser', password='pass1234')

    def test_add_transaction_view(self):
        response = self.client.post(reverse('transactions:add_transaction'), {
            'amount': 200.50,
            'category': 'payment',
            'transaction_type': 'debit'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after adding
        self.assertEqual(Transaction.objects.count(), 1)
        txn = Transaction.objects.first()
        self.assertEqual(txn.amount, 200.50)
        self.assertEqual(txn.user, self.user)

    def test_list_transactions_view(self):
        Transaction.objects.create(
            user=self.user, amount=150.00,
            category='transfer', transaction_type='credit'
        )
        response = self.client.get(reverse('transactions:list_transactions'))
        self.assertContains(response, '150.00')
        self.assertContains(response, 'transfer')

    def test_login_required_for_add(self):
        self.client.logout()
        response = self.client.get(reverse('transactions:add_transaction'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
