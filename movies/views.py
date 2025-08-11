from django.shortcuts import render, redirect, get_object_or_404
from .models import Movie, Theater, Seat, Booking, Show
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q, F
import razorpay
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.http import HttpResponse
from django.utils.timezone import now
from django.contrib import messages
import time
import random

# initialize razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def movie_list(request):
    search_query = request.GET.get('search')
    if search_query:
        movies = Movie.objects.filter(name__icontains=search_query)
    else:
        movies = Movie.objects.all()
        print("Movies fetched:", list(movies))
    return render(request, 'movies/movie_list.html', {'movies': movies})



def theater_list(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)

    theaters = (
        Theater.objects.filter(movie=movie)
        .annotate(
            total_seats=Count('seats', distinct=True),
            booked_seats=Count('seats', filter=Q(seats__is_booked=True), distinct=True),
        )
        .annotate(
            available_seats=F('total_seats') - F('booked_seats')
        )
    )

    # Add boolean flag for template
    for t in theaters:
        t.has_available_seats = t.available_seats > 0

    return render(request, "movies/theater_list.html", {
        "movie": movie,
        "theaters": theaters,
    })

@login_required(login_url='/login/')
def book_seats(request, theater_id):
    theater = get_object_or_404(Theater, id=theater_id)
    seats = Seat.objects.filter(theater=theater)

    if request.method == 'POST':
        selected_seats = request.POST.getlist('seats')
        error_seats = []
        created_bookings = []

        if not selected_seats:
            return render(request, "movies/seat_selection.html", {
                'theaters': theater,
                'seats': seats,
                'error': "No seat selected"
            })

        for seat_id in selected_seats:
            seat = get_object_or_404(Seat, id=seat_id, theater=theater)
            if seat.is_booked:
                error_seats.append(seat.seat_number)
                continue
            try:
                booking = Booking.objects.create(
                    user=request.user,
                    movie=theater.movie,
                    theater=theater,
                    seat=seat,
                    price=seat.price if hasattr(seat, 'price') else 220  # use seat price if available
                )
                # mark seat immediately (signals will also cover this)
                seat.is_booked = True
                seat.save()
                created_bookings.append(booking)
            except IntegrityError:
                error_seats.append(seat.seat_number)

        if error_seats:
            error_message = f"The following seats are already booked: {', '.join(error_seats)}"
            return render(request, 'movies/seat_selection.html', {
                'theaters': theater,
                'seats': seats,
                'error': error_message
            })

        # Redirect to choose payment options for the first booking
        return redirect('payment_options', booking_id=created_bookings[0].id)

    return render(request, 'movies/seat_selection.html', {
        'theaters': theater,
        'seats': seats
    })


@staff_member_required
def admin_dashboard(request):
    # Compute totals and popular items (basic)
    # If you want only confirmed payments counted, filter by appropriate Payment/Booking status
    total_revenue = Booking.objects.aggregate(total=Sum('price'))['total'] or 0
    total_revenue_display = f"{total_revenue:,.2f}"

    popular_movies = (
        Movie.objects.annotate(total_bookings=Count('booking'))
        .order_by('-total_bookings')[:5]
    )
    busy_theaters = (
        Theater.objects.annotate(total_bookings=Count('booking'))
        .order_by('-total_bookings')[:5]
    )

    recent_bookings = Booking.objects.select_related('user', 'movie', 'theater', 'seat') \
                            .order_by('-booked_at')[:10]

    context = {
        'total_revenue': total_revenue_display,
        'popular_movies': popular_movies,
        'popular_movie': popular_movies[0] if popular_movies else None,
        'busy_theaters': busy_theaters,
        'busy_theater': busy_theaters[0] if busy_theaters else None,
        'recent_bookings': recent_bookings,
    }

    return render(request, 'admin_dashboard/dashboard.html', context)


def process_payment(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        # Save user's selected payment method if you want (PaymentOption or field)
        # For UPI/manual methods, treat as confirmed for now (or implement flow)
        if payment_method and payment_method.lower() in ['gpay', 'phonepe', 'paytm']:
            booking.razorpay_order_id = None
            # For manual/UPI flows we mark as "Confirmed" here in views only if you want:
            # booking.status = 'Confirmed'  # only if field exists
            booking.save()

            # Send confirmation email for manual payments
            user_email = booking.user.email
            username = booking.user.username
            movie = booking.movie.name
            theater = booking.theater.name
            seat = booking.seat.seat_number
            show_time = booking.theater.time.strftime('%Y-%m-%d %H:%M')

            subject = f"🎟️ Ticket Booking Confirmation - {movie}"
            body = f"""Hi {username},

Your booking was successful!

Movie: {movie}
Theater: {theater}
Show Time: {show_time}
Seat Number: {seat}
Amount: ₹{booking.price}

Please arrive 15 minutes before the show.

Thank you for booking with BookMySeat!
"""
            # send email (console backend during development)
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user_email], fail_silently=False)

            return render(request, 'movies/payment_success.html', {'booking': booking})

    return redirect('payment_options', booking_id=booking_id)


def initiate_payment(request, booking_id):
    booking = Booking.objects.get(id=booking_id)

    # Create razorpay order
    order_amount = int(booking.price * 100)  # amount in paise
    order_currency = "INR"
    order = razorpay_client.order.create({
        "amount": order_amount,
        "currency": order_currency,
        "payment_capture": 1
    })

    # Save razorpay order id to booking record (so we can relate later)
    booking.razorpay_order_id = order['id']
    booking.save()

    context = {
        'booking': booking,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'payment': order,
        'payment_amount': order.get('amount'),
        'payment_order_id': order.get('id'),
    }

    return render(request, 'movies/payment.html', context)


@csrf_exempt
def payment_success(request):
    """
    Razorpay posts payment details to client handler, which then posts to this view.
    We verify signature here, mark booking and send email.
    """
    if request.method == "POST":
        booking_id = request.POST.get('booking_id')
        razorpay_order_id = request.POST.get('razorpay_order_id')
        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_signature = request.POST.get('razorpay_signature')

        booking = get_object_or_404(Booking, id=booking_id)

        # Verify the payment signature with razorpay
        try:
            razorpay_client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
            # Mark the booking razorpay order id / payment id
            booking.razorpay_order_id = razorpay_order_id
            # optionally store payment id in a Payment model (you have Payment model)
            # Payment.objects.create(booking=booking, amount=booking.price, payment_id=razorpay_payment_id, status='Completed')
            booking.save()

            # Send confirmation email
            user_email = booking.user.email
            username = booking.user.username
            movie = booking.movie.name
            theater = booking.theater.name
            seat = booking.seat.seat_number
            show_time = booking.theater.time.strftime('%Y-%m-%d %H:%M')

            subject = f"🎟️ Booking Confirmed - {movie}"
            body = f"""Hi {username},

Your payment was successful and your booking is confirmed.

Movie: {movie}
Theater: {theater}
Show Time: {show_time}
Seat Number: {seat}
Amount Paid: ₹{booking.price}

Booking ID: {booking.id}

Please arrive 15 minutes before the show.

Thank you for booking with BookMySeat!
"""
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user_email], fail_silently=False)

            return render(request, 'movies/payment_success.html', {'booking': booking})
        except Exception as e:
            # Payment verification failed
            # Optionally record a failed Payment object
            # Payment.objects.create(booking=booking, amount=booking.price, payment_id=razorpay_payment_id or '', status='Failed')
            return render(request, 'movies/payment_failed.html', {'error': str(e)})

    return HttpResponse(status=400)


def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, pk=movie_id)
    votes_count = "129K"
    return render(request, "movies/movie_detail.html", {"movie": movie, "votes_count": votes_count})


def select_seat(request, show_id):
    show = get_object_or_404(Show, id=show_id)
    available_seats = Seat.objects.filter(show=show, is_booked=False)

    if request.method == 'POST':
        selected_seat_ids = request.POST.getlist('selected_seats')
        
        if not selected_seat_ids:
            messages.error(request, "Please select at least one seat.")
            return redirect('seat_selection', show_id=show_id)

        # Double-check if seats are still available
        seats_to_book = Seat.objects.filter(id__in=selected_seat_ids, is_booked=False)
        if seats_to_book.count() != len(selected_seat_ids):
            messages.error(request, "Some seats are no longer available. Please choose again.")
            return redirect('seat_selection', show_id=show_id)

        # Create booking (payment logic should be here or before this)
        booking = Booking.objects.create(show=show, user=request.user)
        booking.seat.set(seats_to_book)  # ManyToMany set

        # Mark them as booked immediately (signals will also run)
        for seat in seats_to_book:
            seat.is_booked = True
            seat.save()

        messages.success(request, "Seats booked successfully!")
        return redirect('payment_page', booking_id=booking.id)

    return render(request, 'movies/seat_selection.html', {
        'show': show,
        'available_seats': available_seats
    })


@login_required
def payment_options(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        if payment_method:
            # Optionally save PaymentOption here
            return redirect('process_payment', booking_id=booking.id)

    return render(request, 'movies/payment_options.html', {'booking': booking})
