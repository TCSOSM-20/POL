all: clean package

clean:
	rm -rf dist deb_dist osm_policy_module-*.tar.gz osm_policy_module.egg-info .eggs

package:
	python3 setup.py --command-packages=stdeb.command sdist_dsc
	cp debian/python3-osm-policy-module.postinst deb_dist/osm-policy-module*/debian
	cd deb_dist/osm-policy-module*/  && dpkg-buildpackage -rfakeroot -uc -us