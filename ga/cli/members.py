from ga.legis import Client, Chamber, get_member, get_members

from ga.cli.sessions import resolve_session
from ga.cli.format import party


def cmd_members(client: Client, args):
    session = resolve_session(client, args.session)
    if args.id is not None:
        m = get_member(client, args.id, session.id)
        print(f"{m.title} {m.name} — District {m.district} ({party(m.party_name)})")
        if m.residence:
            print(f"Residence: {m.residence}")
        if m.occupation:
            print(f"Occupation: {m.occupation}")
        if m.phone:
            print(f"Phone: {m.phone}")
        if m.committees:
            print("\nCommittees:")
            for c in m.committees:
                print(f"  {c.role:30s}  {c.name}")
    else:
        chamber = Chamber[args.chamber.title()] if args.chamber else None
        members = get_members(client, session.id, chamber)
        for m in sorted(members, key=lambda m: (m.chamber_type.value, int(''.join(filter(str.isdigit, m.district)) or 0))):
            print(f"{m.id:5d}  {m.chamber_type.name:6s}  {m.district:5s}  {party(m.party_name)}  {m.city:20s}  {m.name}")
