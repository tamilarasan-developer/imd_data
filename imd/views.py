from datetime import date
from rest_framework.decorators import api_view
from rest_framework.response import Response
from imd.models import imd_data
from .serializers import ImdDataSerializer


@api_view(['GET'])
def imd_data_list(request):

    input_date = request.GET.get('date')
    today = date.today()

    if input_date:
        try:
            # convert string → date
            from datetime import datetime
            start_date = datetime.strptime(input_date, "%Y-%m-%d").date()

            # filter from start_date → today
            data = imd_data.objects.filter(date__range=[start_date, today]).order_by('date')

        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"})
    else:
        # default → today
        data = imd_data.objects.filter(date=today)

    serializer = ImdDataSerializer(data, many=True)
    return Response(serializer.data)