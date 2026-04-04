from django.db import models

class imd_data(models.Model):
    date = models.DateField()
    cluster = models.CharField(max_length=50)

    maximum_past_24hrs = models.FloatField(null=True, blank=True)
    minimum_past_24hrs = models.FloatField(null=True, blank=True)
    average = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField()

    class Meta:
        db_table = "imd_data_chennai"
        managed = False


        
           
    def __str__(self):
        return f"{self.cluster} - {self.date}"