from unittest import TestCase
from unittest.mock import MagicMock, patch

from steampy.client import SteamClient
from steampy.exceptions import SteamResponseError
from steampy.login import LoginExecutor
from steampy.market import SteamMarket
from steampy.models import GameOptions
from steampy.session import SteamSession


def response(status_code: int, payload=None, text: str = ''):
    result = MagicMock()
    result.status_code = status_code
    result.ok = status_code < 400
    result.headers = {}
    result.text = text
    result.url = 'https://steamcommunity.com/example'
    result.request.method = 'GET'
    result.json.return_value = payload
    return result


class TestReliability(TestCase):
    @patch('steampy.session.time.sleep')
    @patch('requests.Session.request')
    def test_safe_get_retries_server_error_with_default_timeout(self, request, sleep) -> None:
        request.side_effect = [response(503), response(200)]

        result = SteamSession().get('https://steamcommunity.com/example')

        assert result.status_code == 200
        assert request.call_count == 2
        assert request.call_args_list[0].kwargs['timeout'] == 30
        sleep.assert_called_once_with(1)

    @patch('requests.Session.request')
    def test_post_server_error_is_not_retried(self, request) -> None:
        request.return_value = response(503)

        with self.assertRaises(SteamResponseError):
            SteamSession().post('https://steamcommunity.com/example')

        request.assert_called_once()

    def test_login_invalid_json_includes_response_diagnostics(self) -> None:
        invalid_response = response(200, text='<html>maintenance</html>')
        invalid_response.json.side_effect = ValueError('invalid JSON')

        with self.assertRaises(SteamResponseError) as error:
            LoginExecutor._get_json(invalid_response, 'Beginning Steam login')

        assert error.exception.status_code == 200
        assert error.exception.url == 'https://steamcommunity.com/example'
        assert error.exception.body_preview == '<html>maintenance</html>'

    def test_cookie_login_extracts_web_token_and_falls_back_to_api_key(self) -> None:
        client = SteamClient('api-key')
        client.steam_guard = {'steamid': '1'}
        client.set_login_cookies({'steamLoginSecure': '1%7C%7Cweb-token', 'sessionid': 'session-id'})
        assert client._access_token == 'web-token'

        api_response = MagicMock()
        api_response.json.return_value = {
            'response': {'trade_offers_received': [], 'trade_offers_sent': []},
        }
        client.api_call = MagicMock(return_value=api_response)
        client.get_trade_offers(merge=False)
        assert client.api_call.call_args.args[-1]['access_token'] == 'web-token'

        client._access_token = None
        client.get_trade_offers(merge=False)
        assert client.api_call.call_args.args[-1]['key'] == 'api-key'

    @patch('steampy.market.ConfirmationExecutor')
    def test_buy_item_confirms_only_the_requested_confirmation(self, executor_class) -> None:
        session = MagicMock()
        session.cookies.get_dict.return_value = {'sessionid': 'session-id'}
        session.post.side_effect = [
            response(200, {'success': 22, 'confirmation': {'confirmation_id': '456'}}),
            response(200, {'wallet_info': {'success': 1}}),
        ]
        market = SteamMarket(session)
        market._set_login_executed({'identity_secret': 'secret', 'steamid': '123'}, 'session-id')
        executor_class.return_value.confirm_by_id.return_value = True

        result = market.buy_item('Example item', 'listing-id', 100, 10, GameOptions.CS)

        assert result['wallet_info']['success'] == 1
        executor_class.return_value.confirm_by_id.assert_called_once_with('456')
