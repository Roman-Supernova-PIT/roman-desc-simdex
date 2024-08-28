INSTALLDIR = test_install

toinstall = server.py import_images.py import_transients.py templates/base.html templates/roman_desc_simdex.html

migrations = migrations/run_migrations.py $(patsubst %,%,$(wildcard migrations/*.sql))

default :
	@echo Do "make install INSTALLDIR=<dir>"
	@echo Dev : make install INSTALLDIR=/global/cfs/cdirs/m4385/spin/roman-desc-simdex/install-dev
	@echo Production : make install INSTALLDIR=/global/cfs/cdirs/m4385/spin/roman-desc-simdex/install

install : $(patsubst %, $(INSTALLDIR)/%, $(toinstall)) $(patsubst %, $(INSTALLDIR)/%, $(migrations))

$(INSTALLDIR)/% : src/%
	install -Dcp $< $@

$(INSTALLDIR)/migrations/% : migrations/%
	install -Dcp $< $@
