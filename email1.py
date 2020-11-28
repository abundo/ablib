#!/usr/bin/env python3
"""
Class to handle sending of HTML formatted email through localhost

Note: module is called email1 to avoid name collision with
      built-in python module email
"""

# python standard modules
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ----- Start of config

# ----- End of config


class Email:

    def send(self, recipient=None, cc=None, sender=None, subject=None, msg=None):
        """
        Send an email through MTA at localhost
        """
        message = MIMEMultipart('alternative')
        message['From'] = sender
        message['To'] = recipient
        if cc:
            message['Cc'] = cc
        message['Subject'] = subject

        part1 = MIMEText(msg, 'html', 'utf-8')

        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart message, in this case
        # the HTML message, is best and preferred.
        message.attach(part1)

        mta = smtplib.SMTP('localhost')
        mta.sendmail(sender, [recipient], message.as_string())
        mta.quit()


def main():
    """
    Function tests
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('cmd', choices=[
        "send_email",
    ])
    parser.add_argument('--recipient', required=True)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--msg', required=True)
    args = parser.parse_args()

    email = Email()
    if args.cmd == 'send_email':
        # msg = args.msg.encode('utf-8', 'surrogateescape')     # make sure msg is utf-8
        email.send(recipient=args.recipient, subject=args.subject, msg=args.msg)

    else:
        print("Unknown cmd %s" % args.cmd)


if __name__ == '__main__':
    main()
