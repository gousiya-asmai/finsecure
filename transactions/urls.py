from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    
    path('add/', views.add_transaction, name='add_transaction'),
    path('list/', views.list_transactions, name='list_transactions'),
    path('predict/', views.predict_view, name='predict_fraud'),
     path('add/', views.TransactionCreateView.as_view(), name='add'),
     path('list/', views.TransactionListView.as_view(), name='list'), 
]
