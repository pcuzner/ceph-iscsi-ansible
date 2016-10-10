Name:           ceph-iscsi-ansible
Version:        1.0
Release:        1%{?dist}
Summary:        Ansible playbooks for deploying LIO iscsi gateways in front of a Ceph cluster
License:        ASL 2.0
URL:            https://github.com/pcuzner/ceph-iscsi-ansible
Source0:        https://github.com/pcuzner/ceph-iscsi-ansible/archive/%{version}/%{name}-%{version}.tar.gz
BuildArch:      noarch

Requires: ansible >= 1.9
Requires: ceph-ansible >= 1.0.5

%description
Ansible playbooks that define nodes as iSCSI gateways (LIO). Once complete, the
LIO instance on each node provides an ISCSI endpoint for clients to connect to.
The playbook defines the front-end iSCSI environment (target -> tpgN ->
NodeACLS/client), as well as the underlying rbd definition for the rbd images
to be exported over iSCSI.

ceph-iscsi-gw.yml ... defines the LIO configuration(defined by
                      group_vars/ceph-iscsi-gw.yml)
purge_gateways.yml .. deletes the LIO configuration, and optionally rbd's from
                      the environment

NB: The playbooks are dependent upon the ceph-iscsi-config package being
installed/available to the hosts that will become iSCSI gateways.

%prep
%setup -q

%build

%install
mkdir -p %{buildroot}%{_datarootdir}/ceph-ansible

for f in group_vars library roles ceph-iscsi-gw.yml purge_gateways.yml; do
  cp -a $f %{buildroot}%{_datarootdir}/ceph-ansible
done

%files
%doc LICENSE
%doc README
%{_datarootdir}/ceph-ansible/ceph-iscsi-gw.yml
%{_datarootdir}/ceph-ansible/purge_gateways.yml
%{_datarootdir}/ceph-ansible/group_vars/ceph-iscsi-gw.sample
%{_datarootdir}/ceph-ansible/roles/ceph-iscsi-gw
%{_datarootdir}/ceph-ansible/library/igw*
%exclude %{_datarootdir}/ceph-ansible/library/igw*.pyo
%exclude %{_datarootdir}/ceph-ansible/library/igw*.pyc

%changelog
* Mon Oct 10 2016 Paul Cuzner <pcuzner@redhat.com> - 1.0-1
- fix : allow client_connections and rbd_devices to be be empty to skip those steps
- add usage guidelines to the group_vars/ceph-iscsi-gw.sample file
- added variable to allow pre-req checks to be bypassed during a run
- updated list of rpm pre-req that ansible checks for
- add synchronize task to the playbook to copy admin keyring to gateway node(s)
- updated igw_purge module to allow for the deletion of the alua port groups

* Thu Oct 06 2016 Paul Cuzner <pcuzner@redhat.com> - 0.8-1
- fix : purge_gateways.yml was missing
- removed packages directory to clean up the source archive
- spec file updates (dependencies)

* Wed Oct 05 2016 Paul Cuzner <pcuzner@redhat.com> - 0.7-1
- removed service dependencies for rbdmap/target (replaced by rbd-target-gw form ceph-iscsi-config rpm)
- removed target overrides files
- updated playbook to add skip_partx yes to multipath.conf

* Mon Oct 03 2016 Paul Cuzner <pcuzner@redhat.com> - 0.6-1
- changed the main function to have an ansible prefix to allow the code to know where it is invoked from
- updated the purge module to support image names being prefixed by a pool i.e. pool/image

* Tue Sep 27 2016 Paul Cuzner <pcuzner@redhat.com> - 0.5-1
- initial rpm package

