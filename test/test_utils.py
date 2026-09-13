from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock, patch

from steampy import utils
from steampy.market import SteamMarket
from steampy.models import GameOptions


class TestUtils(TestCase):
    def test_text_between(self) -> None:
        text = 'var a = "dupadupa";'
        text_between = utils.text_between(text, 'var a = "', '";')
        assert text_between == 'dupadupa'

    def test_texts_between(self) -> None:
        text = '<li>element 1</li>\n<li>some random element</li>'
        items = list(utils.texts_between(text, '<li>', '</li>'))
        assert items == ['element 1', 'some random element']

    def test_account_id_to_steam_id(self) -> None:
        account_id = '358617487'
        steam_id = utils.account_id_to_steam_id(account_id)
        assert steam_id == '76561198318883215'

    def test_steam_id_to_account_id(self) -> None:
        steam_id = '76561198318883215'
        account_id = utils.steam_id_to_account_id(steam_id)
        assert account_id == '358617487'

    def test_get_key_value_from_url(self) -> None:
        url = 'https://steamcommunity.com/tradeoffer/new/?partner=aaa&token=bbb'
        assert utils.get_key_value_from_url(url, 'partner') == 'aaa'
        assert utils.get_key_value_from_url(url, 'token') == 'bbb'

    def test_get_key_value_from_url_case_insensitive(self) -> None:
        url = 'https://steamcommunity.com/tradeoffer/new/?Partner=aaa&Token=bbb'
        assert utils.get_key_value_from_url(url, 'partner', case_sensitive=False) == 'aaa'
        assert utils.get_key_value_from_url(url, 'token', case_sensitive=False) == 'bbb'

    def test_calculate_gross_price(self) -> None:
        steam_fee = Decimal('0.05')  # 5%
        publisher_fee = Decimal('0.1')  # 10%

        assert utils.calculate_gross_price(Decimal('0.01'), publisher_fee, steam_fee) == Decimal('0.03')
        assert utils.calculate_gross_price(Decimal('0.10'), publisher_fee, steam_fee) == Decimal('0.12')
        assert utils.calculate_gross_price(Decimal(100), publisher_fee, steam_fee) == Decimal(115)

    def test_calculate_net_price(self) -> None:
        steam_fee = Decimal('0.05')  # 5%
        publisher_fee = Decimal('0.1')  # 10%

        assert utils.calculate_net_price(Decimal('0.03'), publisher_fee, steam_fee) == Decimal('0.01')
        assert utils.calculate_net_price(Decimal('0.12'), publisher_fee, steam_fee) == Decimal('0.10')
        assert utils.calculate_net_price(Decimal(115), publisher_fee, steam_fee) == Decimal(100)

    def test_market_listings_keep_active_and_pending_sell_listings(self) -> None:
        html = '''
        <div id="myListings">
          <div class="market_home_listing_table">My listings awaiting confirmation
            <div id="mylisting_1"><span title="$1">$1</span><span title="($0.8)">($0.8)</span>
              <div class="market_listing_listed_date">today</div></div>
          </div>
          <div class="market_home_listing_table">My sell listings
            <div id="mylisting_2"><span title="$2">$2</span><span title="($1.6)">($1.6)</span>
              <div class="market_listing_listed_date">today</div></div>
          </div>
        </div>
        '''

        listings = utils.get_market_listings_from_html(html)['sell_listings']

        assert set(listings) == {'1', '2'}
        assert listings['1']['need_confirmation'] is True
        assert listings['2']['need_confirmation'] is False

    @patch('steampy.market.ConfirmationExecutor')
    def test_create_buy_order_retries_after_targeted_mobile_confirmation(self, executor_class) -> None:
        market = SteamMarket(MagicMock())
        market._set_login_executed({'identity_secret': 'secret', 'steamid': '123'}, 'session-id')
        market._session.post.side_effect = [
            MagicMock(json=lambda: {'success': 22, 'confirmation': {'confirmation_id': '456'}}),
            MagicMock(json=lambda: {'success': 1, 'buy_orderid': '789'}),
        ]
        executor_class.return_value.confirm_by_id.return_value = True

        response = market.create_buy_order('Example item', '1.50', 1, GameOptions.CS)

        assert response['buy_orderid'] == '789'
        executor_class.return_value.confirm_by_id.assert_called_once_with('456')
        assert market._session.post.call_args_list[1].kwargs['data']['confirmation'] == '456'
