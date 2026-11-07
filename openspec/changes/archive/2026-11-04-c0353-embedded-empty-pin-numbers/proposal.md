# Preserve empty native pin numbers across embedding targets

Directly embedding a KiCad9 symbol definition in a KiCad10 sheet retains an old raw tilde marker as
a literal pin number. Public flat_hierarchy has six mounting-hole pins whose identity changes from
empty to tilde, producing six new named groups. Fix only the checked symbol embedding text boundary;
retain the complete pin universe, literal tilde identities, existing model and all warnings.
