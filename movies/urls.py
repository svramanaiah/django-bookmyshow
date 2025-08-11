from django.urls import path
from . import views
urlpatterns=[
    path('',views.movie_list,name='movie_list'),
    #path('<int:movie_id>/theaters',views.theater_list,name='theater_list'),
    path('theater/<int:theater_id>/seats/book/',views.book_seats,name='book_seats'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('<int:booking_id>/payment/', views.initiate_payment, name='initiate_payment'),
    path('movie/<int:movie_id>/',views.movie_detail, name='movie_detail'),
    path('movies/<int:movie_id>/theaters/', views.theater_list, name='theater_list'),
    path('select_seats/<int:show_id>/', views.select_seat, name='select_seats'),
    path('payment/options/<int:booking_id>/', views.payment_options, name='payment_options'),
    path('movies/payment/process/<int:booking_id>/', views.process_payment, name='process_payment'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/options/<int:booking_id>/', views.payment_options, name='payment_options'),
    path('payment/success/', views.payment_success, name='payment_success'),
    
]