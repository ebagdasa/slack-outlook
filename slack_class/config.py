"""Configuration settings for running the Python auth samples locally.

In a production deployment, this information should be saved in a database or
other secure storage mechanism.
"""
from secret import *




message_test = {
    "text": "Hi! remember to do your readings for tomorrow!",
    "attachments": [
        {
            "text": "Please press a button to response",
            "fallback": "You are unable to choose a game",
            "callback_id": "wopr_game",
            "color": "#3AA3E3",
            "attachment_type": "default",
            "actions": [
                {
                    "name": "status",
                    "text": "Already Done",
                    "type": "button",
                    "value": "done"
                },
                {
                    "name": "status",
                    "text": "Do it Now",
                    "type": "button",
                    "value": "now"
                },
                {
                    "name": "status",
                    "text": "Will do Later",

                    "type": "select",

                    "options": [
                        {
                            "text": "Remind me in 30 min",
                            "value": "30"
                        },
                        {
                            "text": "Remind me in 3 hours.",
                            "value": "180"
                        },
                        {
                            "text": "Remind me in 6 hours.",
                            "value": "360"
                        },
                        {
                            "text": "Never remind me",
                            "value": "never"
                        },
                    ]
                }
            ]
        }
    ]
}

message_respond = {
    "text": "Hi! remember to do your readings for tomorrow!",
    "attachments": [
        {
            "text": "Please press a button to response \n :white_check_mark: Thank you!",
            "fallback": "You are unable to choose a game",
            "callback_id": "wopr_game",
            "color": "#3AA3E3",
            "attachment_type": "default",
        }
    ]
}