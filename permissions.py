import json, os

class Permissions:

    _permissions = {}
    admin_perm = 'admin'

    def __init__(self, default_admin):
        self.permissions_file_location = "{}{}".format(os.environ['PERMISSIONS_FILE_DIR'], os.environ['PERMISSIONS_FILE_NAME'])
        try: 
            self._permissions = self.permissions
        except FileNotFoundError:
            print("Unable to find permissions. Starting with defaults.")
            self._permissions[self.admin_perm] = [default_admin]

    @property
    def permissions(self):
        if self._permissions is None or len(self._permissions.keys()) == 0:
            with open(self.permissions_file_location, 'r') as perms:
                self._permissions = json.loads(perms.read())
                print(json.dumps(self._permissions, indent=4))
        else:
            return self._permissions

    def save_permissions(self):
        with open(self.permissions_file_location, 'w') as perms:
            perms.write(json.dumps(self.permissions, indent=4))

    def check_permission(self, perm, user):
        print(json.dumps(self.permissions, indent=4))
        return user in self.permissions.get(perm, [])

    def grant_permission(self, perm, granting_user, requesting_user):
        if self.check_permission(self.admin_perm, granting_user):
            if len(self.permissions.get(perm, [])) == 0:
                self.permissions[perm] = [requesting_user]
            else:
                self.permissions[perm].append(requesting_user)
            self.save_permissions()
        else:
            raise PermissionError("You do not have the required permissions to do that.")

    def remove_permission(self, perm, granting_user, requesting_user):
        if self.check_permission(self.admin_perm, granting_user):
            if len(self.permissions.get(perm, [])) > 1:
                self.permissions[perm].remove(requesting_user)
            else:
                del self.permissions[perm]
            self.save_permissions()
        else:
            raise PermissionError("You do not have the required permissions to do that.")