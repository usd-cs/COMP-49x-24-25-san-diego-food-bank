from django import forms
from .models import FAQ, Tag

class FAQForm(forms.ModelForm):
    class Meta:
        model = FAQ
        fields = ['question', 'answer'] # 'tags'
        # widgets = {
        #     'tags': forms.TextInput(attrs={'id': 'tag-search', 'placeholder': 'Search or create tags'}),
        # }