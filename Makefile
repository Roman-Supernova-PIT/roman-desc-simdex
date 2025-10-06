INSTALLDIR = test_install
PG_USER = postgres
PG_PASSWORD = fragile
PG_DB = roman_desc_sims
PG_HOST = postgres
PG_PORT = 5432

toinstall = webserver_config.py server.py import_images.py import_transients.py templates/base.html templates/roman_desc_simdex.html

migrations = migrations/run_migrations.py $(patsubst %,%,$(wildcard migrations/*.sql))

default :
	@echo Do "make install INSTALLDIR=<dir>"
	@echo Dev : make install INSTALLDIR=/global/cfs/cdirs/m4385/spin/roman-desc-simdex/install-dev
	@echo Production : make install INSTALLDIR=/global/cfs/cdirs/m4385/spin/roman-desc-simdex/install

install : $(patsubst %, $(INSTALLDIR)/%, $(toinstall)) $(patsubst %, $(INSTALLDIR)/%, $(migrations))

.PHONY: src/webserver_config.py
src/webserver_config.py:
	echo PG_USER=\"$(PG_USER)\" > src/webserver_config.py
	echo PG_PASSWORD=\"$(PG_PASSWORD)\" >> src/webserver_config.py
	echo PG_DB=\"$(PG_DB)\" >> src/webserver_config.py
	echo PG_HOST=\"$(PG_HOST)\" >> src/webserver_config.py
	echo PG_PORT=\"$(PG_PORT)\" >> src/webserver_config.py

$(INSTALLDIR)/% : src/%
	install -Dcp $< $@

$(INSTALLDIR)/migrations/% : migrations/%
	install -Dcp $< $@
