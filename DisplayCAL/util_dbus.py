"""Utilities for interacting with D-Bus using Gio or dbus.

Provides object access, method calls, properties, and introspection.
"""

# Standard library imports
from __future__ import annotations

import sys

USE_GI = True

DBusException = Exception

if sys.platform not in ("darwin", "win32"):
    if USE_GI:
        try:
            from gi.repository import Gio, GLib
        except ImportError:
            USE_GI = False
    if not USE_GI:
        import dbus
        from dbus.mainloop import glib
    from DisplayCAL.util_xml import XMLDict

    if USE_GI:
        dbus_session = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        dbus_system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

        DBusException = GLib.Error
    else:
        glib.threads_init()

        dbus_session = dbus.SessionBus()
        dbus_system = dbus.SystemBus()

        DBusException = dbus.exceptions.DBusException


from DisplayCAL.util_str import safe_str

BUSTYPE_SESSION = 1
BUSTYPE_SYSTEM = 2


class DBusObjectInterfaceMethod:
    """A class representing a D-Bus object interface method.

    Args:
        iface (object): The D-Bus interface object.
        method_name (str): The name of the D-Bus method.
    """

    def __init__(self, iface: object, method_name: str) -> None:
        self._iface = iface
        self._method_name = method_name

    def __call__(self, *args, **kwargs) -> object:
        """Call the D-Bus method with the given arguments.

        Args:
            *args: Positional arguments to pass to the D-Bus method.
            **kwargs: Keyword arguments to pass to the D-Bus method.

        Returns:
            object: The result of the D-Bus method call.
        """
        if USE_GI:
            format_string = ""
            value = []
            for arg in args:
                if isinstance(arg, str):
                    format_string += "s"
                elif isinstance(arg, int):
                    if arg < 0:
                        format_string += "i"
                    else:
                        format_string += "u"
                elif isinstance(arg, float):
                    format_string += "f"
                else:
                    raise TypeError(f"Unsupported argument type: {type(arg)}")
                value.append(arg)
            args = [f"({format_string})"]
            args.extend(value)
        if "timeout" not in kwargs:
            kwargs["timeout"] = 500
        return getattr(self._iface, self._method_name)(*args, **kwargs)


class DBusObject:
    """A class representing a D-Bus object.

    Args:
        bus_type (int): The type of D-Bus bus (BUSTYPE_SESSION or
            BUSTYPE_SYSTEM).
        bus_name (str): The D-Bus bus name.
        object_path (None | str): The D-Bus object path. If None, it is
            derived from the bus name.
        iface_name (None | str): The D-Bus interface name. If None, the
            bus name is used as the interface name.
    """

    def __init__(
        self,
        bus_type: int,
        bus_name: str,
        object_path: None | str = None,
        iface_name: None | str = None,
    ) -> None:
        self._bus_type = bus_type
        self._bus_name = bus_name
        if object_path is None:
            object_path = "/" + bus_name.replace(".", "/")
        self._object_path = object_path
        self._iface_name = iface_name
        self._proxy = None
        self._iface = None
        if object_path:
            bus = dbus_session if bus_type == BUSTYPE_SESSION else dbus_system
            self._bus = bus
            interface = self._bus_name
            if self._iface_name:
                interface += "." + self._iface_name
            try:
                if USE_GI:
                    self._proxy = Gio.DBusProxy.new_sync(
                        bus,
                        Gio.DBusProxyFlags.NONE,
                        None,
                        bus_name,
                        object_path,
                        interface,
                        None,
                    )
                    self._iface = self._proxy
                else:
                    self._proxy = bus.get_object(bus_name, object_path)
                    self._iface = dbus.Interface(self._proxy, dbus_interface=interface)
            except (TypeError, ValueError, DBusException) as exception:
                raise DBusObjectError(exception, self._bus_name) from exception
        self._introspectable = None

    def __getattr__(self, name: str) -> DBusObjectInterfaceMethod:
        """Get an attribute of the D-Bus object.

        Args:
            name (str): The name of the attribute to get.

        Raises:
            DBusObjectError: If the attribute cannot be accessed.

        Returns:
            DBusObjectInterfaceMethod: The method corresponding to the attribute name.
        """
        name = "".join(part.capitalize() for part in name.split("_"))
        try:
            return DBusObjectInterfaceMethod(self._iface, name)
        except (AttributeError, TypeError, ValueError, DBusException) as exception:
            raise DBusObjectError(exception, self._bus_name) from exception

    @property
    def properties(self) -> dict:
        """Get all properties of the D-Bus object.

        Raises:
            DBusObjectError: If properties cannot be accessed.

        Returns:
            dict: A dictionary of all properties of the D-Bus object.
        """
        if not self._proxy:
            return {}
        interface = self._bus_name
        if self._iface_name:
            interface += f".{self._iface_name}"
        try:
            if USE_GI:
                iface = Gio.DBusProxy.new_sync(
                    self._bus,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    self._bus_name,
                    self._object_path,
                    "org.freedesktop.DBus.Properties",
                    None,
                )
            else:
                iface = dbus.Interface(self._proxy, "org.freedesktop.DBus.Properties")
            return DBusObjectInterfaceMethod(iface, "GetAll")(interface)
        except (TypeError, ValueError, DBusException) as exception:
            raise DBusObjectError(exception, self._bus_name) from exception

    def introspect(self) -> XMLDict:
        """Introspect the D-Bus object to get its XML representation.

        Raises:
            DBusObjectError: If introspection fails.

        Returns:
            XMLDict: An XMLDict representation of the introspected D-Bus object.
        """
        if not self._introspectable:
            self._introspectable = DBusObject(
                self._bus_type,
                "org.freedesktop.DBus",
                "/" + self._bus_name.replace(".", "/"),
                "Introspectable",
            )
        xml = self._introspectable.Introspect()
        return XMLDict(xml)


class DBusObjectError(DBusException):
    """Custom exception class for D-Bus object errors.

    Args:
        exception (Exception): The original exception that occurred.
        bus_name (str | None): The D-Bus bus name associated with the error.
    """

    def __init__(self, exception: Exception, bus_name: None | str = None) -> None:
        self._dbus_error_name = getattr(exception, "get_dbus_name", lambda: None)()
        if self._dbus_error_name == "org.freedesktop.DBus.Error.ServiceUnknown":
            exception = f"{exception}: {bus_name}"
        DBusException.__init__(self, safe_str(exception))

    def get_dbus_name(self) -> None | str:
        """Get the D-Bus error name.

        Returns:
            None | str: The D-Bus error name, or None if not available.
        """
        return self._dbus_error_name
