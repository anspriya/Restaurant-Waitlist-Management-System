# 🍽️ Restaurant Waitlist Management System

A web-based waitlist management system for restaurants that helps manage table reservations, estimated wait times, and real-time customer notifications via SMS. Built with Flask (Python), HTML, CSS, JavaScript, and Twilio for SMS integration.

## 🚀 Features

- 🧾 Customer waitlist registration form
- 🕒 Real-time wait time estimation and countdown
- 📩 SMS notifications to customers when their table is ready (via Twilio)
- 📊 Admin dashboard to view/manage the current waitlist
- 🧠 Auto-remove and notify customers when wait time expires
- ✅ Cancel or leave waitlist at any time


## 🛠️ Tech Stack

| Technology | Description |
|------------|-------------|
| Python + Flask | Backend framework |
| HTML, CSS, JS  | Frontend |
| Twilio API     | SMS notifications |
| SQLite / In-memory Queue | Waitlist storage |

## Project Structure

Restaurant-Waitlist-Management-System/
│
├── static/
│   ├── css/
│   │   ├── about.css              # Styles for the About page
│   │   ├── contact.css            # Styles for the Contact page
│   │   ├── style.css              # General/global styles (if any)
│   │   └── waitliststyle.css      # Styles specific to Waitlist page
│   │
│   └── images/
│       ├── g1.jpg
│       ├── g2.jpg
│       ├── g3.jpeg
│       ├── ig4.jpg                
│       └── img2.jpg
│
├── templates/
│   ├── about.html                 # About Kasata Restaurant
│   ├── contact.html               # Contact details and map
│   ├── index.html                 # Home / Landing page
│   ├── menu.html                  # Menu page
│   └── waitlist.html              # Waitlist status and queue information
│
├── app.py                         # Flask backend app handling routes and waitlist logic
├── README.md                      # Project documentation

