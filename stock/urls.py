from django.urls import path
from . import views

app_name='stock'
urlpatterns = [
    path('', views.dashboard_view, name='stock_analysis'),
    # path('testcase/', views.testcase, name='testcase'),
    # path('<int:todo_id>/delete', views.delete, name='delete'),
    # path('<int:todo_id>/update', views.update, name='update'),
    path('api/category_briefing/', views.api_category_briefing, name='api_category_briefing'),
    # ... 기존 라우터들 ...
    path('bot/', views.bot_dashboard, name='bot_dashboard'),
    path('bot/start/', views.start_bot, name='start_bot'),
    path('bot/stop/', views.stop_bot, name='stop_bot'),
    # path('add/<int:stock_id>/', views.add_tracked_stock, name='add_tracked_stock'),
    # path('remove/<int:stock_id>/', views.remove_tracked_stock, name='remove_tracked_stock'),

    # Ajax API 라우터 (이 부분이 추가되어야 합니다)
    path('api/search/', views.api_search_and_add, name='api_search'),
    path('api/manage/', views.api_manage_tracked, name='api_manage'),
    path('api/analyze_batch/', views.api_run_batch_analysis, name='api_analyze_batch'),
]