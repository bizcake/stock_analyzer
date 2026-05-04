from django.urls import path
from . import views

app_name='stock'
urlpatterns = [
    path('', views.dashboard_view, name='stock_analysis'),

    # Ajax API 라우터 (이 부분이 추가되어야 합니다)
    # path('api/search/', views.api_search_and_add, name='api_search'),
    # path('api/manage/', views.api_manage_tracked, name='api_manage'),
]