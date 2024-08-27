INSTALLDIR = test_install

toinstall = server.py import_images.py templates/base.html templates/roman_desc_simdex.html


default :
	@echo Do "make install INSTALLDIR=<dir>"
	@echo Dev : make install INSTALLDIR=/global/cfs/cdirs/m4385/spin/roman-desc-simdex/install-dev
	@echo Production : make install INSTALLDIR=/global/cfs/cdirs/m4385/spin/roman-desc-simdex/install

install : $(patsubst %, $(INSTALLDIR)/%, $(toinstall))

$(INSTALLDIR)/% : src/%
	install -Dcp $< $@
