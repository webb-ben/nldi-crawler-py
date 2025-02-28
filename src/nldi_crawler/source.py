#!/usr/bin/env python
# coding: utf-8
# pylint: disable=fixme
#
#
"""
routines to manage the table of crawler_sources
"""
import os
import re
import tempfile
import logging
import httpx
import ijson


from sqlalchemy import String, Integer, select
from sqlalchemy.orm import mapped_column
from sqlalchemy.exc import SQLAlchemyError

from .db import NLDI_Base, DataAccessLayer


class CrawlerSource(NLDI_Base):
    """
    An ORM reflection of the crawler_source table

    The crawler_source table is held in the nldi_data schema in the NLDI PostGIS database.
    The schema name and table name are hard-coded to reflect this.

    This object maps properties to columns for a given row of that table. Once this object
    is created, the row's data is instantiated within the object.

    > stmt = select(CrawlerSource)
        .order_by(CrawlerSource.crawler_source_id)
        .where(CrawlerSource.crawler_source_id == 1)
    > for src in session.scalars(stmt):
    ... print(f"{src.crawler_source_id} == {src.source_name}")

    """

    __tablename__ = "crawler_source"
    __table_args__ = {"schema": "nldi_data"}

    crawler_source_id = mapped_column(Integer, primary_key=True)
    source_name = mapped_column(String(64))
    source_suffix = mapped_column(String(16))
    source_uri = mapped_column(String)
    feature_id = mapped_column(String)
    feature_name = mapped_column(String)
    feature_uri = mapped_column(String)
    feature_reach = mapped_column(String)
    feature_measure = mapped_column(String)
    ingest_type = mapped_column(String(16))
    feature_type = mapped_column(String)

    def table_name(self, *args) -> str:
        """
        Getter-like function to return a formatted string representing the table name.

        If an optional positional argument is given, that string is appended to the table name.
        This lets us do things like:

        > self.table_name()
        feature_suffix
        > self.table_name("temp")
        feature_suffix_temp
        > self.table_name("old")
        feature_suffix_old

        :return: name of the table for this crawler_source
        :rtype: string
        """
        # Sanitize the suffix name... only 'word' characters allowed.
        _s = re.sub(r"\W", "_", self.source_suffix)
        if args:
            return "feature_" + _s + "_" + args[0]
        return "feature_" + _s


def list_sources(dal: DataAccessLayer, selector="") -> list:
    """
    Fetches a list of crawler sources from the master NLDI-DB database.  The returned list
    holds one or mor CrawlerSource() objects, which are reflected from the database using
    the sqlalchemy ORM.

    :param connect_string: The db URL used to connect to the database
    :type connect_string: str
    :return: A list of sources
    :rtype: list of CrawlerSource objects
    """
    dal.connect()
    retval = []

    if selector == "":
        stmt = select(CrawlerSource).order_by(CrawlerSource.crawler_source_id)
    else:
        stmt = (
            select(CrawlerSource)
            .where(CrawlerSource.crawler_source_id == selector)
            .order_by(CrawlerSource.crawler_source_id)
        )

    try:
        with dal.Session() as session:
            for source in session.scalars(stmt):
                retval.append(source)
    except SQLAlchemyError as exc:
        logging.warning("Database session error")
        logging.warning(exc)
        raise

    dal.disconnect()
    return retval


def download_geojson(source) -> str:
    """
    Downloads data from the specified source, saving it to a temporary file on local disk.

    :param source: The descriptor for the source.
    :type source: CrawlerSource()
    :return: path name to temporary file
    :rtype: str
    """
    logging.info(" Downloading data from %s ...", source.source_uri)
    fname = "_tmp"
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".geojson",
            prefix=f"CrawlerData_{source.crawler_source_id}_",
            dir=".",
            delete=False,
        ) as tmp_fh:
            fname = tmp_fh.name
            logging.info("Writing to tmp file %s", tmp_fh.name)
            # timeout = 15sec  TODO: make this a tunable
            with httpx.stream(
                "GET", source.source_uri, timeout=60.0, follow_redirects=True
            ) as response:
                for chunk in response.iter_bytes(1024):
                    tmp_fh.write(chunk)
    except IOError:
        logging.exception(" I/O Error while downloading from %s to %s", source.source_uri, fname)
        return None
    except httpx.ReadTimeout:
        logging.critical(" Read TimeOut attempting to download from %s", source.source_uri)
        os.remove(fname)
        return None
    return fname


def validate_src(src: CrawlerSource) -> tuple:
    """
    Examines a specified source to ensure that it downloads, and the returned data is
    proprly formatted and attributed.

    :param src: the source to examine
    :type src: CrawlerSource
    :return: a tuple of two values: A boolean to indicate if validated, and a string holding
             a description of the reason for failure. If validated is True, the reason string
             is zero-length.
    :rtype: tuple
    """
    try:
        with httpx.stream("GET", src.source_uri, timeout=60.0, follow_redirects=True) as response:
            chunk = response.iter_bytes(2 * 2 * 1024)
            # read 2k bytes, to be sure we get a complete feature.
            itm = next(ijson.items(next(chunk), "features.item"))
            fail = None
            if src.feature_reach is not None and src.feature_reach not in itm["properties"]:
                fail = (False, f"Column not found for 'feature_reach' : {src.feature_reach}")
            if src.feature_measure is not None and src.feature_measure not in itm["properties"]:
                fail = (False, f"Column not found for 'feature_measure' : {src.feature_measure}")
            if src.feature_name is not None and src.feature_name not in itm["properties"]:
                fail = (False, f"Column not found for 'feature_name' : {src.feature_name}")
            # A unique feature ID does not have to be in the properties member.  If present,
            # the `id` member is a sibling of `properties`.
            # if src.feature_id is not None and src.feature_id not in itm["properties"]:
            #     fail = (False, f"Column not found for 'feature_id' : {src.feature_id}")
            if src.feature_uri is not None and src.feature_uri not in itm["properties"]:
                fail = (False, f"Column not found for 'feature_uri' : {src.feature_measure}")
            if fail is not None:
                return fail
    except httpx.ReadTimeout:
        return (False, "Network Timeout")
    except KeyError:
        return (False, "Key Error")
    except ijson.JSONError:
        return (False, "Invalid JSON")

    return (True, "")
