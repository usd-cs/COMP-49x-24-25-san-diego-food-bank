# COMP-49x-24-25-San-Diego-Food-Bank - NLP Service Bot

## Overview:

    This system is intended to serve as a service bot that is capable of utilizing NLP (via Twilio) to automate certain caller interactions.
    These include features such as answering FAQs, scheduling appointments, cancelling appointments, rescheduling appointments,
    and rerouting to an operator when necessary or requested. Along with this service comes the admin panel. The admin panel
    is intended to be an application for stakeholders/employees to manage and update the capabilities and knowledge of this
    service bot system. It is a Django application designed to accommodate several capabilities and features to provide keen
    insights about the system's performance as well as control over it. There is user authentication and access control against
    unrestricted and unapproved individuals. The featured pages of this web application that assist the voice bot service are as
    follows, which will be discussed in more detail below: Audit Logs, FAQs, Monitoring, and Account Approval.

## Features:

    - Audit Logs: TODO
    -FAQs: Admins can create and manage FAQs here. This includes assigning question-answer as well as tags
    for easy sorting and searching. Along with this customization, it contains deletion, modification, and
    addition capabilities for them. These FAQs are the buckets by which the system will attempt to place a
    customer's FAQ request into for appropriate answering.
    - Monitoring: TODO
    - Account Approval: TODO
    - Scheduling: (TODO remove this I'm assuming unless we want to explain how each feature of the bot works) Users can interact with the bot to scheduling appointments for the foodbank. This interacts with the scheduling service, Acuity, and ensures various constraints like <= 20 participants per slot, 2 week scheduling-out periods, and confirmation of scheduling via sms. All interactions are tracked for quality purposes.

## Software Dependencies

    Below are the API Keys required to run the application, along with instructions on how to generate them
        - Twilio:
            1) TODO (instructions for setting up account + getting api key)
            https://login.twilio.com/u/signup?state=hKFo2SBYZEsxUjhwejJKSzVTMFVqbGZ4R1RiVVY4Tm9nWDlZYaFur3VuaXZlcnNhbC1sb2dpbqN0aWTZIGtOOHBPY1ZWeFBNQUs5M0lmS0xVNWNoZDZQX0FwWVJ3o2NpZNkgTW05M1lTTDVSclpmNzdobUlKZFI3QktZYjZPOXV1cks
        - OpenAI:
            1) TODO (instructions for setting up account + getting api key)
        - Google Cloud:
            1) TODO (instructions for setting up account + getting api key)
            https://cloud.google.com/translate/docs/setup

## Running the Application

Prior to running this application, it is based on the assumption that you are already set up with the software dependencies
listed above, you have generated your API keys and have a Twilio phone number assigned to your account.

1. Clone the repo:

   https://github.com/usd-cs/COMP-49x-24-25-san-diego-food-bank.git

   or

   git@github.com:usd-cs/COMP-49x-24-25-san-diego-food-bank.git

2. Install Docker

   https://www.docker.com/products/docker-desktop/

3. Ensure the Docker app that you just downloaded is open, open a terminal, and type the following to connect your Docker account
   (Replace your username with whatever username you just used to sign up)

   docker login -u <username>

5. Update .env files

    TODO - describe how (pasting api keys you generated into the .env file)

6. Start ngrok


7. Copy and paste ngrok link into Twilio URL and save the configuration

8. Running Docker

   Open a new terminal, separate from the one that is running ngrok

   (First time running application)

           docker compose up --build

   (Then run this, but if it is not your first time, then you can skip straight to this command to start the application)

           docker compose up

10. Once the build is complete, visit http://127.0.0.1:8000 to access the admin panel via browser

   (To terminate Docker run the below command)
           docker compose down

    To terminate ngrok, navigate to the terminal it is running in and ctrl-C or cmd-C
