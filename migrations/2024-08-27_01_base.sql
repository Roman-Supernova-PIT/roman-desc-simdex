CREATE TABLE pointing(
   num     int primary key,
   ra      double precision,
   dec     double precision,
   filter  text,
   exptime real,
   mjd     double precision,
   pa       double precision
);
CREATE INDEX ix_q3c_pointing_radec ON sca(q3c_ang2ipix(ra, dec));
CREATE INDEX ix_pointing_filter ON sca(filter);
CREATE INDEX ix_pointing_exptime ON sca(exptime);
CREATE INDEX ix_pointing_mjd ON sca(mjd);

CREATE TABLE sca(
   _pk      serial primary key,
   pointing int,
   scanum   int,
   ra       double precision,
   dec      double precision,
   ra_00    real,
   dec_00   real,
   ra_01    real,
   dec_01   real,
   ra_10    real,
   dec_10   real,
   ra_11    real,
   dec_11   real,
   minra    real,
   maxra    real,
   mindec   real,
   maxdec   real.
);
CREATE INDEX ix_sca_pointing ON sca(pointing);
CREATE INDEX ix_q3c_sca_radec ON sca(q3c_ang2ipix(ra, dec));
CREATE INDEX ix_sca_minra ON sca(minra);
CREATE INDEX ix_sca_maxra ON sca(maxra);
CREATE INDEX ix_sca_mindec ON sca(mindec);
CREATE INDEX ix_sca_maxcdec ON sca(maxdec);

CREATE TABLE transient(
   id                     bigint primary key,
   healpix                int,
   ra                     double precision,
   dec                    double precision,
   host_id                bigint,
   gentype                int,
   model_name             text,
   start_mjd              real,
   end_mjd                real,
   z_cmb                  real,
   mw_ebv                 real,
   mw_extinction_applied  boolean,
   av                     real,
   rv                     real,
   v_pec                  real,
   host_ra                double precision,
   host_dec               double precision,
   host_mag_g             real,
   host_mag_i             real,
   hsot_mag_f             real,
   host_sn_sep            real,
   peak_mjd               real,
   peak_mag_g             real,
   peak_mag_i             real,
   peak_mag_f             real,
   lens_dmu               real,
   lens_dmu_applied       boolean,
   model_params           jsonb
);
CREATE INDEX ix_q3c_transient_radec ON transient(q3c_ang2ipix(ra, dec));
CREATE INDEX ix_q3c_transient_hostradec ON transient(q3c_ang2ipix(host_ra, host_dec));
CREATE INDEX ix_transient_healpix ON transient(healpix);
CREATE INDEX ix_transient_hostid ON transient(host_id);
CREATE INDEX ix_transient_gentype ON transient(gentype);
CREATE INDEX ix_transient_z_cmb ON transient(z_cmb);
CREATE INDEX ix_transient_host_mag_g ON transient(host_mag_g);
CREATE INDEX ix_transient_host_mag_i ON transient(host_mag_i);
CREATE INDEX ix_transient_host_mag_f ON transient(host_mag_f);
CREATE INDEX ix_transient_peak_mag_g ON transient(peak_mag_g);
CREATE INDEX ix_transient_peak_mag_i ON transient(peak_mag_i);
CREATE INDEX ix_transient_peak_mag_f ON transient(peak_mag_f);
CREATE INDEX ix_transient_peak_mjd ON transient(peak_mjd);
CREATE INDEX ix_transient_start_mjd ON transient(start_mjd);
CREATE INDEX ix_transient_end_mjd ON transient(end_mjd);
