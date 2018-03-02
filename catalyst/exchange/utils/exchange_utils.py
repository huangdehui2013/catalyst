import hashlib
import json
import os
import pickle
import shutil
from datetime import date, datetime

import pandas as pd
from catalyst.assets._assets import TradingPair
from six import string_types
from six.moves.urllib import request

from catalyst.constants import DATE_FORMAT, SYMBOLS_URL
from catalyst.exchange.exchange_errors import ExchangeSymbolsNotFound, \
    InvalidHistoryFrequencyError, InvalidHistoryFrequencyAlias
from catalyst.exchange.utils.serialization_utils import ExchangeJSONEncoder, \
    ExchangeJSONDecoder, ConfigJSONEncoder
from catalyst.utils.paths import data_root, ensure_directory, \
    last_modified_time
from catalyst.exchange.utils.datetime_utils import get_periods_range


def get_sid(symbol):
    """
    Create a sid by hashing the symbol of a currency pair.

    Parameters
    ----------
    symbol: str

    Returns
    -------
    int
        The resulting sid.

    """
    sid = int(
        hashlib.sha256(symbol.encode('utf-8')).hexdigest(), 16
    ) % 10 ** 6
    return sid


def get_exchange_folder(exchange_name, environ=None):
    """
    The root path of an exchange folder.

    Parameters
    ----------
    exchange_name: str
    environ:

    Returns
    -------
    str

    """
    if not environ:
        environ = os.environ

    root = data_root(environ)
    exchange_folder = os.path.join(root, 'exchanges', exchange_name)
    ensure_directory(exchange_folder)

    return exchange_folder


def is_blacklist(exchange_name, environ=None):
    exchange_folder = get_exchange_folder(exchange_name, environ)
    filename = os.path.join(exchange_folder, 'blacklist.txt')

    return os.path.exists(filename)


def get_exchange_config_filename(exchange_name, environ=None):
    """
    The absolute path of the exchange's symbol.json file.

    Parameters
    ----------
    exchange_name:
    environ:

    Returns
    -------
    str

    """
    name = 'config.json'
    exchange_folder = get_exchange_folder(exchange_name, environ)
    return os.path.join(exchange_folder, name)


def download_exchange_config(exchange_name, filename, environ=None):
    """
    Downloads the exchange's symbols.json from the repository.

    Parameters
    ----------
    exchange_name: str
    environ:

    Returns
    -------
    str

    """
    url = EXCHANGE_CONFIG_URL.format(exchange=exchange_name)
    request.urlretrieve(url=url, filename=filename)


def get_exchange_config(exchange_name, filename=None, environ=None):
    """
    The de-serialized content of the exchange's config.json.

    Parameters
    ----------
    exchange_name: str
    is_local: bool
    environ:

    Returns
    -------
    Object

    """
    if filename is None:
        filename = get_exchange_config_filename(exchange_name)

    if os.path.isfile(filename):
        now = pd.Timestamp.utcnow()
        limit = pd.Timedelta('2H')
        if pd.Timedelta(now - last_modified_time(filename)) > limit:
            download_exchange_config(exchange_name, filename, environ)

    else:
        download_exchange_config(exchange_name, filename, environ)

    with open(filename) as data_file:
        try:
            data = json.load(data_file, cls=ExchangeJSONDecoder)
            return data

        except ValueError:
            return dict()

def save_exchange_config(exchange_name, config, filename=None, environ=None):
    """
    Save assets into an exchange_config file.

    Parameters
    ----------
    exchange_name: str
    config
    environ

    Returns
    -------

    """
    if filename is None:
        name = 'config.json'
        exchange_folder = get_exchange_folder(exchange_name, environ)
        filename = os.path.join(exchange_folder, name)

    with open(filename, 'w+') as handle:
        json.dump(config, handle, indent=4, cls=ConfigJSONEncoder)


def get_symbols_string(assets):
    """
    A concatenated string of symbols from a list of assets.

    Parameters
    ----------
    assets: list[TradingPair]

    Returns
    -------
    str

    """
    array = [assets] if isinstance(assets, TradingPair) else assets
    return ', '.join([asset.symbol for asset in array])


def get_exchange_auth(exchange_name, alias=None, environ=None):
    """
    The de-serialized contend of the exchange's auth.json file.

    Parameters
    ----------
    exchange_name: str
    environ:

    Returns
    -------
    Object

    """
    exchange_folder = get_exchange_folder(exchange_name, environ)
    name = 'auth' if alias is None else alias
    filename = os.path.join(exchange_folder, '{}.json'.format(name))

    if os.path.isfile(filename):
        with open(filename) as data_file:
            data = json.load(data_file)
            return data
    else:
        data = dict(name=exchange_name, key='', secret='')
        with open(filename, 'w') as f:
            json.dump(data, f, sort_keys=False, indent=2,
                      separators=(',', ':'))
            return data


def delete_algo_folder(algo_name, environ=None):
    """
    Delete the folder containing the algo state.

    Parameters
    ----------
    algo_name: str
    environ:

    Returns
    -------
    str

    """
    folder = get_algo_folder(algo_name, environ)
    shutil.rmtree(folder)


def get_algo_folder(algo_name, environ=None):
    """
    The algorithm root folder of the algorithm.

    Parameters
    ----------
    algo_name: str
    environ:

    Returns
    -------
    str

    """
    if not environ:
        environ = os.environ

    root = data_root(environ)
    algo_folder = os.path.join(root, 'live_algos', algo_name)
    ensure_directory(algo_folder)

    return algo_folder


def get_algo_object(algo_name, key, environ=None, rel_path=None, how='pickle'):
    """
    The de-serialized object of the algo name and key.

    Parameters
    ----------
    algo_name: str
    key: str
    environ:
    rel_path: str
    how: str

    Returns
    -------
    Object

    """
    if algo_name is None:
        return None

    folder = get_algo_folder(algo_name, environ)

    if rel_path is not None:
        folder = os.path.join(folder, rel_path)

    name = '{}.p'.format(key) if how == 'pickle' else '{}.json'.format(key)
    filename = os.path.join(folder, name)

    if os.path.isfile(filename):
        if how == 'pickle':
            with open(filename, 'rb') as handle:
                return pickle.load(handle)

        else:
            with open(filename) as data_file:
                data = json.load(data_file, cls=ExchangeJSONDecoder)
                return data

    else:
        return None


def save_algo_object(algo_name, key, obj, environ=None, rel_path=None,
                     how='pickle'):
    """
    Serialize and save an object by algo name and key.

    Parameters
    ----------
    algo_name: str
    key: str
    obj: Object
    environ:
    rel_path: str
    how: str

    """
    folder = get_algo_folder(algo_name, environ)

    if rel_path is not None:
        folder = os.path.join(folder, rel_path)
        ensure_directory(folder)

    if how == 'json':
        filename = os.path.join(folder, '{}.json'.format(key))
        with open(filename, 'wt') as handle:
            json.dump(obj, handle, indent=4, cls=ExchangeJSONEncoder)

    else:
        filename = os.path.join(folder, '{}.p'.format(key))
        with open(filename, 'wb') as handle:
            pickle.dump(obj, handle, protocol=pickle.HIGHEST_PROTOCOL)


def get_algo_df(algo_name, key, environ=None, rel_path=None):
    """
    The de-serialized DataFrame of an algo name and key.

    Parameters
    ----------
    algo_name: str
    key: str
    environ:
    rel_path: str

    Returns
    -------
    DataFrame

    """
    folder = get_algo_folder(algo_name, environ)

    if rel_path is not None:
        folder = os.path.join(folder, rel_path)

    filename = os.path.join(folder, key + '.csv')

    if os.path.isfile(filename):
        try:
            with open(filename, 'rb') as handle:
                return pd.read_csv(handle, index_col=0, parse_dates=True)
        except IOError:
            return pd.DataFrame()
    else:
        return pd.DataFrame()


def save_algo_df(algo_name, key, df, environ=None, rel_path=None):
    """
    Serialize to csv and save a DataFrame by algo name and key.

    Parameters
    ----------
    algo_name: str
    key: str
    df: pd.DataFrame
    environ:
    rel_path: str

    """
    folder = get_algo_folder(algo_name, environ)
    if rel_path is not None:
        folder = os.path.join(folder, rel_path)
        ensure_directory(folder)

    filename = os.path.join(folder, key + '.csv')

    with open(filename, 'wt') as handle:
        df.to_csv(handle, encoding='UTF_8')


def clear_frame_stats_directory(algo_name):
    """
    remove the outdated directory
    to avoid overloading the disk

    Parameters
    ----------
    algo_name: str

    Returns
    -------
    error: str

    """
    error = None
    algo_folder = get_algo_folder(algo_name)
    folder = os.path.join(algo_folder, 'frame_stats')
    if os.path.exists(folder):
        try:
            shutil.rmtree(folder)
        except OSError:
            error = 'unable to remove {}, the analyze ' \
                    'data will be inconsistent'.format(folder)
    return error


def remove_old_files(algo_name, today, rel_path, environ=None):
    """
    remove old files from a directory
    to avoid overloading the disk

    Parameters
    ----------
    algo_name: str
    today: Timestamp
    rel_path: str
    environ:

    Returns
    -------
    error: str

    """

    error = None
    algo_folder = get_algo_folder(algo_name, environ)
    folder = os.path.join(algo_folder, rel_path)
    ensure_directory(folder)

    # run on all files in the folder
    for f in os.listdir(folder):
        try:
            file_path = os.path.join(folder, f)
            creation_unix = os.path.getctime(file_path)
            creation_time = pd.to_datetime(creation_unix, unit='s', utc=True)

            # if the file is older than 30 days erase it
            if today - pd.DateOffset(30) > creation_time:
                os.unlink(file_path)
        except OSError:
            error = 'unable to erase files in {}'.format(folder)

    return error


def get_exchange_minute_writer_root(exchange_name, environ=None):
    """
    The minute writer folder for the exchange.

    Parameters
    ----------
    exchange_name: str
    environ:

    Returns
    -------
    BcolzExchangeBarWriter

    """
    exchange_folder = get_exchange_folder(exchange_name, environ)

    minute_data_folder = os.path.join(exchange_folder, 'minute_data')
    ensure_directory(minute_data_folder)

    return minute_data_folder


def get_exchange_bundles_folder(exchange_name, environ=None):
    """
    The temp folder for bundle downloads by algo name.

    Parameters
    ----------
    exchange_name: str
    environ:

    Returns
    -------
    str

    """
    exchange_folder = get_exchange_folder(exchange_name, environ)

    temp_bundles = os.path.join(exchange_folder, 'temp_bundles')
    ensure_directory(temp_bundles)

    return temp_bundles


def has_bundle(exchange_name, data_frequency, environ=None):
    exchange_folder = get_exchange_folder(exchange_name, environ)

    folder_name = '{}_bundle'.format(data_frequency.lower())
    folder = os.path.join(exchange_folder, folder_name)

    return os.path.isdir(folder)


def perf_serial(obj):
    """
    JSON serializer for objects not serializable by default json code

    Parameters
    ----------
    obj: Object

    Returns
    -------
    str

    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    raise TypeError("Type %s not serializable" % type(obj))


def get_common_assets(exchanges):
    """
    The assets available in all specified exchanges.

    Parameters
    ----------
    exchanges: list[Exchange]

    Returns
    -------
    list[TradingPair]

    """
    symbols = []
    for exchange_name in exchanges:
        s = [asset.symbol for asset in exchanges[exchange_name].get_assets()]
        symbols.append(s)

    inter_symbols = set.intersection(*map(set, symbols))

    assets = []
    for symbol in inter_symbols:
        for exchange_name in exchanges:
            asset = exchanges[exchange_name].get_asset(symbol)
            assets.append(asset)

    return assets


def resample_history_df(df, freq, field, start_dt=None):
    """
    Resample the OHCLV DataFrame using the specified frequency.

    Parameters
    ----------
    df: DataFrame
    freq: str
    field: str

    Returns
    -------
    DataFrame

    """
    if field == 'open':
        agg = 'first'
    elif field == 'high':
        agg = 'max'
    elif field == 'low':
        agg = 'min'
    elif field == 'close':
        agg = 'last'
    elif field == 'volume':
        agg = 'sum'
    else:
        raise ValueError('Invalid field.')

    resampled_df = df.resample(
        freq, closed='left', label='left'
    ).agg(agg)  # type: pd.DataFrame

    # Because the samples are closed left, we get one more candle at
    # the beginning then the requested number for bars. Removing this
    # candle to avoid confusion.
    if start_dt and not resampled_df.empty:
        resampled_df = resampled_df[resampled_df.index >= start_dt]

    return resampled_df


def from_ms_timestamp(ms):
    return pd.to_datetime(ms, unit='ms', utc=True)


def get_epoch():
    return pd.to_datetime('1970-1-1', utc=True)


def group_assets_by_exchange(assets):
    exchange_assets = dict()
    for asset in assets:
        if asset.exchange not in exchange_assets:
            exchange_assets[asset.exchange] = list()

        exchange_assets[asset.exchange].append(asset)

    return exchange_assets


def get_catalyst_symbol(market_or_symbol):
    """
    The Catalyst symbol.

    Parameters
    ----------
    market_or_symbol

    Returns
    -------

    """
    if isinstance(market_or_symbol, string_types):
        parts = market_or_symbol.split('/')
        return '{}_{}'.format(parts[0].lower(), parts[1].lower())

    else:
        return '{}_{}'.format(
            market_or_symbol['base'].lower(),
            market_or_symbol['quote'].lower(),
        )


def save_asset_data(folder, df, decimals=8):
    symbols = df.index.get_level_values('symbol')
    for symbol in symbols:
        symbol_df = df.loc[(symbols == symbol)]  # Type: pd.DataFrame

        filename = os.path.join(folder, '{}.csv'.format(symbol))
        if os.path.exists(filename):
            print_headers = False

        else:
            print_headers = True

        with open(filename, 'a') as f:
            symbol_df.to_csv(
                path_or_buf=f,
                header=print_headers,
                float_format='%.{}f'.format(decimals),
            )


def forward_fill_df_if_needed(df, periods):
    df = df.reindex(periods)
    # volume should always be 0 (if there were no trades in this interval)
    df['volume'] = df['volume'].fillna(0.0)
    # ie pull the last close into this close
    df['close'] = df.fillna(method='pad')
    # now copy the close that was pulled down from the last timestep
    # into this row, across into o/h/l
    df['open'] = df['open'].fillna(df['close'])
    df['low'] = df['low'].fillna(df['close'])
    df['high'] = df['high'].fillna(df['close'])
    return df


def transform_candles_to_df(candles):
    return pd.DataFrame(candles).set_index('last_traded')


def get_candles_df(candles, field, freq, bar_count, end_dt=None):
    all_series = dict()

    for asset in candles:
        asset_df = transform_candles_to_df(candles[asset])
        rounded_end_dt = end_dt.round(freq)

        periods = get_periods_range(
            start_dt=None, end_dt=rounded_end_dt,
            freq=freq, periods=bar_count
        )

        if rounded_end_dt > end_dt:
            periods = periods[:-1]
        elif rounded_end_dt <= end_dt:
            periods = periods[1:]

        # periods = pd.date_range(end=end_dt, periods=bar_count, freq=freq)
        asset_df = forward_fill_df_if_needed(asset_df, periods)

        all_series[asset] = pd.Series(asset_df[field])

    df = pd.DataFrame(all_series)

    df.dropna(inplace=True)

    return df
