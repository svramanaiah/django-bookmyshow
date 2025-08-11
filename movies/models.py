from django.db import models
from django.contrib.auth.models import User 


class Movie(models.Model):
    name= models.CharField(max_length=255)
    image= models.ImageField(upload_to="movies/")
    rating = models.DecimalField(max_digits=3,decimal_places=1)
    cast= models.TextField()
    description= models.TextField(blank=True,null=True) 
    language = models.CharField(max_length=100)
    release_date = models.DateField()
    duration = models.CharField(max_length=20, default="2h 0m")
    genre = models.CharField(max_length=100)
    director = models.CharField(max_length=100)
    trailer = models.URLField(blank=True, null=True) 
    is_3d = models.BooleanField(default=False)
    is_2d = models.BooleanField(default=True)
    is_IMAX = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name
    @property
    def language_list(self):
        return [lang.strip() for lang in self.language.split(',')]
    
    @property
    def trailer_embed_url(self):
        if self.trailer:
            if 'v=' in self.trailer:
                video_id = self.trailer.split('v=')[1].split('&')[0]
                return f'https://www.youtube.com/embed/{video_id}'
            elif 'youtu.be/' in self.trailer:
                video_id = self.trailer.split('youtu.be/')[1].split('?')[0]
                return f'https://www.youtube.com/embed/{video_id}'
        return ''




class Theater(models.Model):
    name = models.CharField(max_length=255)
    movie = models.ForeignKey(Movie,on_delete=models.CASCADE,related_name='theaters')
    time= models.DateTimeField()

    def __str__(self):
        return f'{self.name} - {self.movie.name} at {self.time}'

    def is_seat_available(self):
        return self.seats.filter(is_booked=False).exists()

class Seat(models.Model):
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name='seats')
    seat_number = models.CharField(max_length=10)
    is_booked = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=150.00)  

    def __str__(self):
        return f'{self.seat_number} in {self.theater.name}'

class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE)
    booked_at = models.DateTimeField(auto_now_add=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} booked {self.seat} for {self.movie}"
    


class Show(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE)
    language = models.CharField(max_length=20)
    screen_format = models.CharField(max_length=10)  # e.g., '2D', '3D'
    start_time = models.DateTimeField()

    def __str__(self):
        return f"{self.movie.name} at {self.theater.name} - {self.screen_format} ({self.language})"
class Payment(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Completed', 'Completed'), ('Failed', 'Failed')], default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for {self.booking} - {self.status}"

class PaymentMethod(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name        
class PaymentOption(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    method = models.ForeignKey(PaymentMethod, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.method.name} for {self.booking} - {self.amount}"
    
