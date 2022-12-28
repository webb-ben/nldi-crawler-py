#!/usr/bin/env python
# coding: utf-8
# pylint: disable=fixme
"""
Test suite.
"""
import os
import click.testing
import pytest

import nldi_crawler

from nldi_crawler import cli
from nldi_crawler import sources


def test_successful_import():
    """Does the module import at all?"""
    assert nldi_crawler.__version__ is not None


def test_main_succeeds():
    """main() runs with no args and yields a zero exit code."""
    runner = click.testing.CliRunner()
    result = runner.invoke(cli.main)
    assert result.exit_code == 0


def test_toml_config():
    """parse cfg file"""
    _test_dir = os.path.dirname(os.path.realpath(__file__))
    cfg = cli.cfg_from_toml(os.path.join(_test_dir, r"cfg-test-1.toml"))
    assert cfg is not None
    assert cfg["NLDI_DB_NAME"] == "test1"
    assert cfg["NLDI_DB_USER"] == "nldi_schema_owner"


def test_toml_broken_config():
    """parse cfg file"""
    _test_dir = os.path.dirname(os.path.realpath(__file__))
    cfg = cli.cfg_from_toml(os.path.join(_test_dir, r"cfg-test-2.toml"))
    ## This config file does not have an 'nldi-db' section, so the config dict should be empty.
    with pytest.raises(KeyError):
        assert cfg["NLDI_DB_NAME"] == "test1"
        assert cfg["NLDI_DB_PASS"] == "changeMe"


def test_env_config():
    """set cfg options from environment"""
    os.environ["NLDI_DB_NAME"] = "SET"
    os.environ["NLDI_DB_PASS"] = "secret"
    cfg = cli.cfg_from_env()
    assert cfg["NLDI_DB_NAME"] == "SET"
    assert cfg["NLDI_DB_PASS"] == "secret"


def test_main_w_config():
    """main() runs with no args and yields a zero exit code."""
    _test_dir = os.path.dirname(os.path.realpath(__file__))
    runner = click.testing.CliRunner()
    result = runner.invoke(cli.main, args=["--config", os.path.join(_test_dir, "cfg-test-1.toml")])
    assert result.exit_code == 0


def test_list_sources():
    """get table of sources from db"""
    _test_dir = os.path.dirname(os.path.realpath(__file__))
    cfg = cli.cfg_from_toml(os.path.join(_test_dir, "..", r"nldi-crawler.toml"))
    _url = cli.db_url(cfg)
    srcs = sources.fetch_source_table(_url)
    assert len(srcs) >= 1


def test_find_source():
    """get table of sources from db"""
    _test_dir = os.path.dirname(os.path.realpath(__file__))
    cfg = cli.cfg_from_toml(os.path.join(_test_dir, "..", r"nldi-crawler.toml"))
    _url = cli.db_url(cfg)
    srcs = sources.fetch_source_table(_url, selector="13")
    assert len(srcs) == 1


def test_no_such_source():
    """get table of sources from db"""
    _test_dir = os.path.dirname(os.path.realpath(__file__))
    cfg = cli.cfg_from_toml(os.path.join(_test_dir, "..", r"nldi-crawler.toml"))
    _url = cli.db_url(cfg)
    srcs = sources.fetch_source_table(_url, selector="00")
    assert len(srcs) == 0


def test_download_source():
    """get table of sources from db"""
    _test_dir = os.path.dirname(os.path.realpath(__file__))
    cfg = cli.cfg_from_toml(os.path.join(_test_dir, "..", r"nldi-crawler.toml"))
    _url = cli.db_url(cfg)
    srcs = sources.fetch_source_table(_url, selector="10")
    fname = sources.download_geojson(srcs[-1])
    assert os.path.exists(fname)
    os.remove(fname)


def test_source_properties():
    """property methods"""
    _test_dir = os.path.dirname(os.path.realpath(__file__))
    cfg = cli.cfg_from_toml(os.path.join(_test_dir, "..", r"nldi-crawler.toml"))
    _url = cli.db_url(cfg)
    src = sources.fetch_source_table(_url, selector="10")[0]
    assert src.source_suffix == "vigil"
    assert src.table_name() == "feature_vigil"
    assert src.table_name("temp") == "feature_vigil_temp"
    assert src.table_name("old") == "feature_vigil_old"
