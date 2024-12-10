from django import forms
from .models import FAQ, Tag

class FAQForm(forms.ModelForm):
    existing_tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        label="Existing Tags",
    )
    new_tags = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Add new tags, comma-separated'}),
        required=False,
        label="New Tags",
    )
    class Meta:
        model = FAQ
        fields = ['question', 'answer', 'existing_tags', 'new_tags']