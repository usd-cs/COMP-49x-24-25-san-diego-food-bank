# COMP-49x-24-25-San-Diego-Food-Bank

## Overview:
    This admin panel is intended to be an application for employees to manage and update the
    capabilities and knowledge of this service bot system. It is a Django application designed to
    accomodate a number of capabilities and features to provide keen insights about the system's
    performance as well as control over it. It is intended for the use of food bank administration ONLY so
    emphasis has been placed on user authentication and access control against unrestricted
    individuals. The feature pages of this web application for the system are as follows which will 
    be discussed in more detail below: Audit logs, FAQs, Monitoring, and System Management.

## Features:

    -FAQs: Admins can create and manage FAQs here. This includes assigning question-answer as well as tags
    for easy sorting and searching. Along with this customization, it contains deletion, modification, and 
    addition capabilities for them. These FAQs are the buckets by which the system will attempt to place a 
    customer's FAQ request into for appropriate answering.

## Installation:

1. Clone the repo:
   
   https://github.com/usd-cs/COMP-49x-24-25-san-diego-food-bank.git

   or
   
   git@github.com:usd-cs/COMP-49x-24-25-san-diego-food-bank.git

2. Install Docker
   
   https://www.docker.com/products/docker-desktop/

3. Connect docker account

   docker login -u <username>

4. Run the application

   (first time running) docker compose up --build

   (any other time) docker compose up

7. Visit http://127.0.0.1:8000 to access via browser

   (end application) docker compose down
    
