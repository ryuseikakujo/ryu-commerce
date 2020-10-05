from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View
from django.utils import timezone
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
import stripe
import random
import string

from .models import Item, OrderItem, Order, Address, Payment, Coupon, Refund, Address, UserProfile
from .forms import CheckoutForm, CouponForm, RefundForm, PaymentForm

# Create your views here.

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))

def is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False
    return valid


class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            form = CheckoutForm()
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True,
            }

            shipping_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='S',
                default=True
            )
            if shipping_address_qs.exists():
                context.update({'default_shipping_address': shipping_address_qs[0]})

            billing_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='B',
                default=True
            )
            if billing_address_qs.exists():
                context.update({'default_billing_address': billing_address_qs[0]})

            return render(self.request, 'checkout.html', context)
        except ObjectDoesNotExist:
            messages.info(self.request, 'You do not have an active order')
            return redirect('core:checkout')

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        # print(self.request.POST)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():

                use_default_shipping = form.cleaned_data.get('use_default_shipping')
                if use_default_shipping:
                    print('Using the default shipping address')
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='S',
                        default=True
                    )
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.warning(self.request, 'No default shipping address available')
                        return redirect('core:checkout')
                else:
                    print('User is entering a new shipping address')
                    shipping_address1 = form.cleaned_data.get('shipping_address')
                    shipping_address2 = form.cleaned_data.get('shipping_address2')
                    shipping_country = form.cleaned_data.get('shipping_country')
                    shipping_zip = form.cleaned_data.get('shipping_zip')

                    if is_valid_form([shipping_address1, shipping_country, shipping_zip]):
                        shipping_address = Address(
                            user = self.request.user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            country=shipping_country,
                            zip=shipping_zip,
                            address_type='S'
                        )
                        shipping_address.save()

                        order.shipping_address = shipping_address
                        order.save()

                        set_default_shipping = form.cleaned_data.get('set_default_shipping')
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save()
                    else:
                        messages.warning(self.request, 'Please fill in the required shipping address fields')
                        return redirect('core:checkout')


                use_default_billing = form.cleaned_data.get('use_default_billing')
                same_billing_address = form.cleaned_data.get('same_billing_address')
                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.pk = None
                    billing_address.save()
                    billing_address.address_type = 'B'
                    billing_address.save()
                    order.billing_address = billing_address
                    order.save()
                    
                elif use_default_billing:
                    print('Using the default billing address')
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='B',
                        default=True
                    )
                    if address_qs.exists():
                        billing_address = address_qs[0]
                        order.billing_address = billing_address
                        order.save()
                    else:
                        messages.warning(self.request, 'No default billing address available')
                        return redirect('core:checkout')
                else:
                    print('User is entering a new billing address')
                    billing_address1 = form.cleaned_data.get('billing_address')
                    billing_address2 = form.cleaned_data.get('billing_address2')
                    billing_country = form.cleaned_data.get('billing_country')
                    billing_zip = form.cleaned_data.get('billing_zip')

                    if is_valid_form([billing_address1, billing_country, billing_zip]):
                        billing_address = Address(
                            user=self.request.user,
                            street_address=billing_address1,
                            apartment_address=billing_address2,
                            country=billing_country,
                            zip=billing_zip,
                            address_type='B'
                        )
                        billing_address.save()

                        order.billing_address = billing_address
                        order.save()

                        set_default_billing = form.cleaned_data.get('set_default_billing')
                        if set_default_billing:
                            billing_address.default = True
                            billing_address.save()
                    else:
                        messages.warning(self.request, 'Please fill in the required billing address fields')
                        return redirect('core:checkout')

                payment_option = form.cleaned_data.get('payment_option')

                if payment_option == 'S':
                    return redirect('core:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment', payment_option='paypal')
                else:
                    messages.warning(self.request, 'Invalid payment option selected')
                return redirect('core:checkout')
            messages.warning(self.request, 'Failed checkout')
            return redirect('core:checkout')
        except ObjectDoesNotExist:
            messages.warning(self.request, 'You do not have an active order')
            return redirect('core:order-summary')

# def checkout(request):
#     return render(request, 'checkout.html')

class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                'order': order,
                'STRIPE_PUBLIC_KEY' : settings.STRIPE_PUBLIC_KEY,
                'DISPLAY_COUPON_FORM': False
            }
            userprofile = UserProfile.objects.get(user=self.request.user)
            # userprofile = self.request.user.userprofile
            if userprofile.one_click_purchasing:
                cards = stripe.Customer.list_sources(
                    userprofile.stripe_customer_id,
                    limit=3,
                    object='card'
                )
                card_list = cards['data']
                if len(card_list) > 0:
                    context.update({
                        'card': card_list[0]
                    })
            return render(self.request, 'payment.html', context)
        else:
            messages.warning(self.request, 'You have not added a billing address')
            return redirect('core:checkout')

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        form = PaymentForm(self.request.POST)
        userprofile = UserProfile.objects.get(user=self.request.user)
        if form.is_valid():
            token = form.cleaned_data.get('stripeToken')
            save = form.cleaned_data.get('save')
            use_default = form.cleaned_data.get('use_default')

            if save:
                if userprofile.stripe_customer_id != '' and  userprofile.stripe_customer_id is not None:
                    customer = stripe.Customer.retrieve(userprofile.stripe_customer_id)
                    customer.sources.create(source=token)
                
                else:
                    customer = stripe.Customer.create(email=self.request.user.email)
                    customer.sources.create(source=token)
                    userprofile.stripe_customer_id = customer['id']
                    userprofile.one_click_purchasing = True
                    userprofile.save()
            
            amount = int(order.get_total() * 100) #cents

            try:
                if use_default or save:
                    charge = stripe.Charge.create(
                        amount=amount,
                        currency="usd",
                        customer=userprofile.stripe_customer_id
                    )
                else:
                    charge = stripe.Charge.create(
                        amount=amount,
                        currency="usd",
                        source=token
                    )

                payment = Payment()
                payment.stripe_charge_id = charge['id']
                payment.user = self.request.user
                payment.amount = order.get_total()
                payment.save()

                order_items = order.items.all()
                order_items.update(ordered=True)
                for item in order_items:
                    item.save()

                order.ordered = True
                order.payment = payment
                order.ref_code = create_ref_code()
                order.save()

                messages.success(self.request, 'Your order was successful!')
                return redirect('/')

            except stripe.error.CardError as e:
            # Since it's a decline, stripe.error.CardError will be caught
                body = e.json_body
                err = body.get('error', {})
                messages.warning(self.request, f'{err.get("message")}')
                return redirect('/')
            except stripe.error.RateLimitError as e:
            # Too many requests made to the API too quickly
                messages.warning(self.request, 'Rate limit error')
                return redirect('/')
            except stripe.error.InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
                messages.warning(self.request, 'Invalid parameters')
                print(e)
                return redirect('/')
            except stripe.error.AuthenticationError as e:
            # Authentication with Stripe's API failed
            # (maybe you changed API keys recently)
                messages.warning(self.request, 'Not authenticated')
                return redirect('/')
            except stripe.error.APIConnectionError as e:
            # Network communication with Stripe failed
                messages.warning(self.request, 'Network error')
                return redirect('/')
            except stripe.error.StripeError as e:
            # Display a very generic error to the user, and maybe send
            # yourself an email
                messages.warning(self.request, 'Something went wrong. You were not charged. Please try again.')
                return redirect('/')
            except Exception as e:
            # Something else happened, completely unrelated to Stripe
                messages.warning(self.request, 'A serious error occurred. We have been notified.')
                print(e)
                return redirect('/')
        
        messages.warning(self.request, 'Invalid data received')
        return redirect('/payment/stripe/')


class HomeView(ListView):
    model = Item
    paginate_by = 2
    template_name = 'home.html'
    context_object_name = 'items'

# def home(request):
#     context = {
#         'items': Item.objects.all()
#     }
#     return render(request, 'home.html', context)

class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.warning(self.request, 'You do not have an active order')
            return redirect('/')


class ItemDetailView(DetailView):
    model = Item
    template_name = 'product.html'
    context_object_name = 'item'

@login_required
def add_to_cart(request, pk):
    item = get_object_or_404(Item, pk=pk)
    order_item, created= OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )
    order_queryset = Order.objects.filter(user=request.user, ordered=False)
    if order_queryset.exists():
        order = order_queryset[0]
        if order.items.filter(item__pk=item.pk).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, 'This item quantity was updated.')
            return redirect('core:order-summary')
        else:
            order.items.add(order_item)
            messages.info(request, 'This item was added to your cart.')
            return redirect('core:order-summary')
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, 'This item quantity was added to your cart.')
    return redirect('core:order-summary')

@login_required
def remove_from_cart(request, pk):
    item = get_object_or_404(Item, pk=pk)
    order_queryset = Order.objects.filter(user=request.user, ordered=False)
    if order_queryset.exists():
        print('order_queryset is ', order_queryset[0])
        order = order_queryset[0]
        if order.items.filter(item__pk=item.pk).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            order.items.remove(order_item)
            order_item.delete()
            messages.info(request, 'This item was removed from your cart.')
            return redirect('core:order-summary')
        else:
            messages.info(request, 'This item was not in your cart.')
            return redirect('core:product', pk=pk)
    else:
        messages.info(request, 'You do not have an active order')
        return redirect('core:product', pk=pk)


@login_required
def remove_single_item_from_cart(request, pk):
    item = get_object_or_404(Item, pk=pk)
    order_queryset = Order.objects.filter(user=request.user, ordered=False)
    if order_queryset.exists():
        print('order_queryset is ', order_queryset[0])
        order = order_queryset[0]
        if order.items.filter(item__pk=item.pk).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, 'This item quantity was updated')
            return redirect('core:order-summary')
        else:
            messages.info(request, 'This item was not in your cart')
            return redirect('core:product', pk=pk)
    else:
        messages.info(request, 'You do not have an active order')
        return redirect('core:product', pk=pk)


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon

    except ObjectDoesNotExist:
        messages.info(request, 'This coupon does not exist')
        return redirect('core:checkout')

class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, 'Successfully added coupon')
                return redirect('core:checkout')

            except ObjectDoesNotExist:
                messages.info(self.request, 'You do not have an active order')
                return redirect('core:checkout')



class RequestResultView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, 'request_refund.html', context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')

            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()

                messages.success(self.request, 'Your request was received')
                return redirect('core:request-refund')

            except ObjectDoesNotExist:
                messages.warning(self.request, 'This order does not exist')
                return redirect('core:request-refund')


class HistoryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.filter(user=self.request.user, ordered=True, refund_granted=False)
            context = {
                'objects': order
            }
            return render(self.request, 'history.html', context)
        except ObjectDoesNotExist:
            messages.warning(self.request, 'No purchase history')
            return redirect('/')

