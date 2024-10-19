
from flask import Flask, render_template, request, jsonify
from collections import deque
from datetime import datetime, timedelta
from twilio.rest import Client
import logging
import threading
import time

app = Flask(__name__)

# Initialize Twilio client for SMS notifications
account_sid = "AC82956768bd6d8b1b7e243f4477d18e43"
auth_token = 'e7709d8c13f9ccb1f52116653d8f6893'
twilio_phone = "+19013905770"
client = Client(account_sid, auth_token)

# Queue to hold customer waitlist info
waitlist = deque()

# Function to calculate wait time based on position in queue
def calculate_wait_time(position):
    average_time_per_table = 2  # minutes per table
    return position * average_time_per_table

# Function to check and notify customers
def check_waitlist():
    while True:
        current_time = datetime.now()
        if waitlist:
            customer = waitlist[0]  # Peek at the first customer
            join_time = datetime.strptime(customer['join_time'], '%Y-%m-%d %H:%M:%S')
            wait_time = timedelta(minutes=customer['wait_time'])
            if current_time >= join_time + wait_time:
                waitlist.popleft()  # Remove the first customer
                notify_customer(customer)
        time.sleep(60)  # Check every minute

def notify_customer(customer):
    try:
        message_body = f"Hello {customer['name']}, Grab your spot in 10 mins at Kasata Restaurant!!"
        message = client.messages.create(
            body=message_body,
            from_=twilio_phone,
            to=customer['phone']
        )
        logging.debug(f"SMS successfully sent: {message.sid}")
    except Exception as e:
        logging.error(f"Error sending SMS: {str(e)}")

# Route to render the index page
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

# Route to render the waitlist page with name and position
@app.route('/join_waitlist')
def waitlist_page():
    name = request.args.get('name')
    position = request.args.get('position')
    return render_template('waitlist.html', name=name, position=position)

# Route to handle joining the waitlist
@app.route('/waitlist', methods=['POST'])
def join_waitlist():
    try:
        data = request.json
        if not all(key in data for key in ('name', 'phone', 'party_size')):
            logging.error('Missing information in the request')
            return jsonify({'message': 'Missing information'}), 400
        
        position = len(waitlist) + 1
        wait_time = calculate_wait_time(position)
        
        customer = {
            'name': data['name'],
            'phone': data['phone'],
            'party_size': data['party_size'],
            'join_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'wait_time': wait_time
        }
        
        waitlist.append(customer)
        logging.debug(f"Added customer: {customer}")  # Log customer details for confirmation
        return jsonify({'message': 'You have been added to the waitlist', 'position': position, 'name': customer['name'], 'wait_time': wait_time})

    except Exception as e:
        logging.error(f"Error in join_waitlist: {str(e)}")
        return jsonify({'message': str(e)}), 500
    
@app.route('/cancel_waitlist', methods=['POST'])
def cancel_waitlist():
    try:
        data = request.json
        name = data['name']
        global waitlist
        waitlist = deque([customer for customer in waitlist if customer['name'] != name])
        logging.debug(f"Cancelled waitlist for customer: {name}")
        return jsonify({'message': 'Waitlist cancelled'}), 200
    except Exception as e:
        logging.error(f"Error cancelling waitlist: {str(e)}")
        return jsonify({'message': 'Error cancelling waitlist'}), 500


# Start the background thread to check the waitlist
background_thread = threading.Thread(target=check_waitlist)
background_thread.daemon = True
background_thread.start()

if __name__ == '__main__':
    app.run(debug=True)
