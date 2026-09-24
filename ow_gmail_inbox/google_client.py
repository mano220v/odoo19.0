"""Fixed-host Google transport; errors never include response bodies or tokens."""
import requests


class GoogleError(Exception):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


def google_request(method, url, *, access_token=None, data=None, params=None, json=None, sending=False):
    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = "Bearer " + access_token
    try:
        response = requests.request(method, url, headers=headers, data=data, params=params,
                                    json=json, timeout=(5, 20), allow_redirects=False)
    except requests.RequestException as exc:
        message = ("Google did not confirm the send result. Check Sent mail before retrying to avoid duplicates."
                   if sending else "Google could not be reached. Please try again shortly.")
        raise GoogleError(message) from exc
    if not 200 <= response.status_code < 300:
        messages = {
            400: "Google rejected this request. Check the search or message details; reconnect if authorization has expired.",
            401: "Your Gmail authorization has expired. Please reconnect your Google account.",
            403: "Google denied this request. Enable the Gmail API and grant the requested mailbox permission.",
            404: "This Gmail message or attachment no longer exists.",
            429: "Google's request limit was reached. Wait a moment before trying again.",
        }
        message = messages.get(response.status_code, "Google could not complete this request. Please try again later.")
        if sending and response.status_code >= 500:
            message = "Google did not confirm delivery. Check Sent mail before retrying to avoid duplicates."
        raise GoogleError(message, response.status_code)
    if not response.content:
        return {}
    try:
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except ValueError as exc:
        raise GoogleError("Google returned an unreadable response. Please try again.") from exc
