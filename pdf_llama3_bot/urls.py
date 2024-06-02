from app.views import *
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',login_page,name="login_page"),
    path('login',login_page,name="login_page"),
    path('login_check',login_check,name='login_check'),
    path('register',register,name='register'),
    path('register_new_user',register_new_user,name='register_new_user'),
    path('logout_user',logout_user,name='logout_user'),
    path('prompt',prompt,name='prompt'),
    path('file_upload',file_upload,name='file_upload'),
    path('home/<str:message>',home,name='home'),
    path('delete_document',delete_document,name='delete_document')
]
