from django.shortcuts import redirect
from django.views import generic

class IndexView(generic.ListView):

    def get(self, request, *args, **kwargs):
        return redirect('/stock')

# def index(request):
#     return redirect('/todos')