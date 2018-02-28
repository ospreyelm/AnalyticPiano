# convert to straight apostrophes
s/’/'/g

# spell all pitches as in D minor
s/([< x])bff/\1a/g
s/([< x])fss/\1g/g
s/([< x])css/\1d/g
s/([< x])gss/\1a/g
s/([< x])dss/\1e/g
s/([< x])cf'/\1b/g
s/([< x])cf/\1b,/g
s/([< x])df/\1cs/g
s/([< x])ds/\1ef/g
s/([< x])es/\1f/g
s/([< x])ff/\1e/g
s/([< x])gf/\1fs/g
s/([< x])af/\1gs/g
s/([< x])as/\1bf/g
s/([< x])bs,/\1c/g
s/([< x])bs/\1c'/g

# generate MIDI numbers
# C8
 s/([< x])c'''''/\1108/g
# C7--B7
 s/([< x])c''''/\196/g
s/([< x])cs''''/\197/g
 s/([< x])d''''/\198/g
s/([< x])ef''''/\199/g
 s/([< x])e''''/\1100/g
 s/([< x])f''''/\1101/g
s/([< x])fs''''/\1102/g
 s/([< x])g''''/\1103/g
s/([< x])gs''''/\1104/g
 s/([< x])a''''/\1105/g
s/([< x])bf''''/\1106/g
 s/([< x])b''''/\1107/g
# C6--B6
 s/([< x])c'''/\184/g
s/([< x])cs'''/\185/g
 s/([< x])d'''/\186/g
s/([< x])ef'''/\187/g
 s/([< x])e'''/\188/g
 s/([< x])f'''/\189/g
s/([< x])fs'''/\190/g
 s/([< x])g'''/\191/g
s/([< x])gs'''/\192/g
 s/([< x])a'''/\193/g
s/([< x])bf'''/\194/g
 s/([< x])b'''/\195/g
# C5--B5
 s/([< x])c''/\172/g
s/([< x])cs''/\173/g
 s/([< x])d''/\174/g
s/([< x])ef''/\175/g
 s/([< x])e''/\176/g
 s/([< x])f''/\177/g
s/([< x])fs''/\178/g
 s/([< x])g''/\179/g
s/([< x])gs''/\180/g
 s/([< x])a''/\181/g
s/([< x])bf''/\182/g
 s/([< x])b''/\183/g
# C4--B4
 s/([< x])c'/\160/g
s/([< x])cs'/\161/g
 s/([< x])d'/\162/g
s/([< x])ef'/\163/g
 s/([< x])e'/\164/g
 s/([< x])f'/\165/g
s/([< x])fs'/\166/g
 s/([< x])g'/\167/g
s/([< x])gs'/\168/g
 s/([< x])a'/\169/g
s/([< x])bf'/\170/g
 s/([< x])b'/\171/g
# A0--B0
 s/([< x])a,,,/\121/g
s/([< x])bf,,,/\122/g
 s/([< x])b,,,/\123/g
# C1--B1
 s/([< x])c,,/\124/g
s/([< x])cs,,/\125/g
 s/([< x])d,,/\126/g
s/([< x])ef,,/\127/g
 s/([< x])e,,/\128/g
 s/([< x])f,,/\129/g
s/([< x])fs,,/\130/g
 s/([< x])g,,/\131/g
s/([< x])gs,,/\132/g
 s/([< x])a,,/\133/g
s/([< x])bf,,/\134/g
 s/([< x])b,,/\135/g
# C2--B2
 s/([< x])c,/\136/g
s/([< x])cs,/\137/g
 s/([< x])d,/\138/g
s/([< x])ef,/\139/g
 s/([< x])e,/\140/g
 s/([< x])f,/\141/g
s/([< x])fs,/\142/g
 s/([< x])g,/\143/g
s/([< x])gs,/\144/g
 s/([< x])a,/\145/g
s/([< x])bf,/\146/g
 s/([< x])b,/\147/g
# C3--B3
 s/([< x])c([> ])/\148\2/g
s/([< x])cs([> ])/\149\2/g
 s/([< x])d([> ])/\150\2/g
s/([< x])ef([> ])/\151\2/g
 s/([< x])e([> ])/\152\2/g
 s/([< x])f([> ])/\153\2/g
s/([< x])fs([> ])/\154\2/g
 s/([< x])g([> ])/\155\2/g
s/([< x])gs([> ])/\156\2/g
 s/([< x])a([> ])/\157\2/g
s/([< x])bf([> ])/\158\2/g
 s/([< x])b([> ])/\159\2/g

# discard any duration information
# s/(<[ x0-9]*>)[0-9]+/\1/g

# introduce line breaks between chords
s/>([whqrd0-9]*) *</>\1,\
</g

# prepare visible and hidden categories and rhythm property
# with Lilypond duration information of 1, 2, or 4
s/ *<([ x0-9]*)>1/    \{"visible":[\1],"hidden":[],"rhythmValue":"w"}/g
s/ *<([ x0-9]*)>2/    \{"visible":[\1],"hidden":[],"rhythmValue":"h"}/g
s/ *<([ x0-9]*)>4/    \{"visible":[\1],"hidden":[],"rhythmValue":"q"}/g
# with Vexflow duration information of w, h, or q
s/ *<([ x0-9]*)>w/    \{"visible":[\1],"hidden":[],"rhythmValue":"w"}/g
s/ *<([ x0-9]*)>h/    \{"visible":[\1],"hidden":[],"rhythmValue":"h"}/g
s/ *<([ x0-9]*)>q/    \{"visible":[\1],"hidden":[],"rhythmValue":"q"}/g
# discard unspported duration information
s/ *<([ x0-9]*)>([whqrd0-9]+)/    \{"visible":[\1],"hidden":[]}/g
# without duration information
s/ *<([ x0-9]*)>/    \{"visible":[\1],"hidden":[]}/g

# use commas, not spaces, to separate notes in array
s/([x0-9]+) +([x0-9]+)/\1,\2/g
s/([x0-9]+) +([x0-9]+)/\1,\2/g
s/\[ +/[/g
s/ +\]/]/g
