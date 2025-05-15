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

    - Audit Logs: Admins can monitor all of the calls that come in to the phone number associated with this bot 
    to ensure that it is working as intended. The audit logs display various components of each phone call such as the call duration, call date, and call transcripts between the bot and the caller. These logs also allow the admin to filter calls based on a specific phone number or date to provide more control.

    -FAQs: Admins can create and manage FAQs here. This includes assigning question-answer as well as tags
    for easy sorting and searching. Along with this customization, it contains deletion, modification, and
    addition capabilities for them. These FAQs are the buckets by which the system will attempt to place a
    customer's FAQ request into for appropriate answering.

    - Monitoring: The monitoring page operates as a metric display for the admins to utilize and identify 
    key insights based on the call system. There are several charts and displays to demonstrate how callers are interacting with the call service, and provide admins with statistics such as the total calls, total calls made in each language, and so forth. There are 2 buttons, the topic button which allows admins to filter the monitoring page charts by certain topics (FAQs, scheduling, etc.) and a time filter button to allow admins to filter the page by Year, Month, or Day. 

    - Account Approval: In the account approval page, superadmins, or certain food bank employees with special approval access, can utilize this page to accept any food bank admin who wishes to use this dashboard. To uphold security, this page functions as a gatekeeper to allow any superuser to accept, or deny, an admin based on their food bank credentials to allow them to log into this dashboard. 

    - Scheduling: (TODO remove this I'm assuming unless we want to explain how each feature of the bot works) Users can interact with the bot to schedule appointments for the foodbank. This service is intended to interact with the scheduling service and can ensure various constraints like <= 20 participants per slot, 2 week scheduling-out periods, and confirmation of scheduling via sms. All interactions are tracked for quality purposes.

## Software Dependencies

    Below are the API Keys required to run the application, along with instructions on how to generate them
        - Twilio:
            1) Sign up: go to https://login.twilio.com/u/signup?state=hKFo2SBTclhJZG5jdHdJc0ROa2kxSFJnR2JUeU12Z2xPUWdTeqFur3VuaXZlcnNhbC1sb2dpbqN0aWTZIEE3WTR5QWdxSUdlLWlKWnoyV3hqdHdkeHRlTlFFOVpBo2NpZNkgTW05M1lTTDVSclpmNzdobUlKZFI3QktZYjZPOXV1cks 

            2) Get your credentials: In the Twilio Console under Settings -> General, copy your Account SID and Auth Token 

            3) Buy a phone number: In Phone Numbers (on the left hand side of the page) -> Buy a number (choose one with Voice & SMS)

            4) Configure webhook (come back to this when you get your NGROK URL)
                - Under Phone Numbers -> Manage -> Active Numbers, click your number 
                - In the voice configuration page, paste your NGROK URL + /init_answer/ to the ender of it and click save
 
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
    - Create 3 files in the root of the project (at the same directory level as the README): twilio.env, gpt.env, google.env
      
        MAKE SURE NOT TO COMMIT THESE FILES TO THE GIT REPOSITORY AS THEY ARE SENSITIVE CREDENTIALS
      
      The content of these files should look like the following:
      
    -twilio.env:

            TWILIO_ACCOUNT_SID=<PASTE ACCOUNT SID HERE>
            TWILIO_AUTH_TOKEN=<PASTE AUTH TOKEN HERE>
            TWILIO_PHONE_NUMBER=<PASTE PHONE NUMBER HERE>
    - gpt.env:

            OPENAI_API_KEY="<PASTE API KEY HERE>"

7. Starting ngrok

    Run the following command in your terminal:

           ngrok http 8000

   (then follow the steps in the twilio setup to paste this link)

10. Running Docker

   Open a new terminal, separate from the one that is running ngrok (Ensure the docker app is open/running)

   (First time running application)

           docker compose up --build

   (Then run this, but if it is not your first time, then you can skip straight to this command to start the application)

           docker compose up

11. Once the build is complete, visit http://127.0.0.1:8000 to access the admin panel via browser

   (To terminate Docker run the below command)
           docker compose down

    To terminate ngrok, navigate to the terminal it is running in and ctrl-C or cmd-C
