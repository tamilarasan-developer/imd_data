from django.urls import path
from .views import imd_data_list

urlpatterns = [
    path('imd-data/', imd_data_list),
]