from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import StockMaster, MyTrackedStock

class StockMasterResource(resources.ModelResource):
    class Meta:
        model = StockMaster
        import_id_fields = ('ticker',)
        fields = ('ticker', 'name_kr', 'name_en', 'market')

class MyTrackedStockResource(resources.ModelResource):
    stock = fields.Field(
        column_name='ticker',
        attribute='stock',
        widget=ForeignKeyWidget(StockMaster, 'ticker')
    )

    class Meta:
        model = MyTrackedStock
        import_id_fields = ('stock',)
        fields = ('stock', 'created_at')
